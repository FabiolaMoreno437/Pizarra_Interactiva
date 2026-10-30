import grpc
from concurrent import futures
import threading
import asyncio
import websockets
import json
import board_pb2
import board_pb2_grpc
from flask import Flask, send_from_directory
import os

# === Parte 1: gRPC server ===

clients = []

class BoardService(board_pb2_grpc.BoardServiceServicer):
    def SendStroke(self, request, context):
        print(f"Recibido trazo de {request.user_id}: ({request.x}, {request.y})")
        for client in clients:
            client.put(request)
        return board_pb2.Ack(message="Stroke recibido")

    def StreamStrokes(self, request, context):
        from queue import Queue
        q = Queue()
        clients.append(q)
        try:
            while True:
                stroke = q.get()
                yield stroke
        except Exception:
            clients.remove(q)

def iniciar_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    board_pb2_grpc.add_BoardServiceServicer_to_server(BoardService(), server)
    server.add_insecure_port('0.0.0.0:50051')
    server.start()
    print("Servidor gRPC en puerto 50051")
    server.wait_for_termination()

# === Parte 2: WebSocket server ===

connected_clients = {}
chat_history = []
draw_history = []

channel = grpc.insecure_channel('localhost:50051')
stub = board_pb2_grpc.BoardServiceStub(channel)

event_loop = asyncio.get_event_loop()

def listen_to_grpc():
    print("[gRPC Listener] Iniciando escucha de trazos...")
    for stroke in stub.StreamStrokes(board_pb2.User(user_id="websocket-server")):
        print(f"[gRPC Listener] Trazado recibido: {stroke.user_id} -> ({stroke.x}, {stroke.y})")
        data = json.dumps({
            "type": "draw",
            "user_id": stroke.user_id,
            "x": stroke.x,
            "y": stroke.y,
            "color": stroke.color,
            "size": stroke.size
        })
        draw_history.append(json.loads(data))
        asyncio.run_coroutine_threadsafe(broadcast(data), event_loop)


async def handler(websocket):
    user_id = None

    try:
        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "join":
                requested_name = data["user_id"]

                # Verificar si el nombre ya esta en uso
                if requested_name in connected_clients.values():
                    await websocket.send(json.dumps({
                        "type": "reject",
                        "user_id": requested_name
                    }))
                    return

                user_id = requested_name
                connected_clients[websocket] = user_id

                # Enviar historial de mensajes y trazos
                for past in chat_history:
                    await websocket.send(json.dumps(past))
                for draw in draw_history:
                    await websocket.send(json.dumps(draw))

                # Enviar al nuevo usuario la lista de los que ya estan conectados
                for uid in connected_clients.values():
                    if uid != user_id:
                        await websocket.send(json.dumps({
                            "type": "join",
                            "user_id": uid
                        }))

                # Difundir que este nuevo usuario se conecto
                await broadcast(json.dumps({
                    "type": "join",
                    "user_id": user_id
                }))

                continue

            if user_id is None:
                continue

            if data["type"] == "draw":
                stroke = board_pb2.Stroke(
                    user_id=data["user_id"],
                    x=int(data["x"]),
                    y=int(data["y"]),
                    color=data["color"],
                    size=int(data["size"])
                )
                stub.SendStroke(stroke)

            elif data["type"] == "clear":
                draw_history.clear()
                await broadcast(json.dumps(data))

            elif data["type"] == "chat":
                to_user = data["to_user_id"] if "to_user_id" in data else ""
                chat_entry = {
                    "type": "chat",
                    "user_id": user_id,
                    "message": data["message"],
                    "to_user_id": to_user
                }
                chat_history.append(chat_entry)

                if to_user:
                    # Enviar solo a destinatario y emisor (unicast)
                    for ws, uid in connected_clients.items():
                        if uid == to_user or uid == user_id:
                            await ws.send(json.dumps(chat_entry))
                else:
                    # Enviar a todos (broadcast)
                    await broadcast(json.dumps(chat_entry))


    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        if user_id:
            del connected_clients[websocket]
            await broadcast(json.dumps({
                "type": "leave",
                "user_id": user_id
            }))

async def broadcast(message):
    for ws in list(connected_clients.keys()):
        try:
            await ws.send(message)
        except:
            del connected_clients[ws]

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Servidor WebSocket en ws://0.0.0.0:8765")
        await asyncio.Future()

# === Parte 3: Servidor HTTP con Flask para servir HTML ===

app = Flask(__name__)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

def iniciar_http():
    app.run(host="0.0.0.0", port=5000)

# === MAIN ===

if __name__ == "__main__":
    threading.Thread(target=iniciar_grpc, daemon=True).start()
    threading.Thread(target=listen_to_grpc, daemon=True).start()
    threading.Thread(target=iniciar_http, daemon=True).start()
    event_loop.run_until_complete(main())