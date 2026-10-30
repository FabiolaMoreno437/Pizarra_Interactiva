bat_script = """@echo off
set PORT=8765

REM Buscar el PID que usa el puerto
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo Cerrando proceso en el puerto %PORT% (PID %%a)...
    taskkill /PID %%a /F > nul 2>&1
)

REM Iniciar el servidor
echo Iniciando servidor...
python server_web.py
pause
"""

file_path = "/mnt/data/iniciar_servidor_con_liberacion.bat"
with open(file_path, "w", encoding="utf-8") as f:
    f.write(bat_script)

file_path
