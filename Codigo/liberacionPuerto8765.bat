# El entorno se reinició, recreamos el archivo BAT para liberar el puerto 8765
bat_code = """@echo off
set PORT=8765

echo Buscando procesos que usan el puerto %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo Cerrando proceso en el puerto %PORT% (PID %%a)...
    taskkill /PID %%a /F > nul 2>&1
)

echo Puerto liberado. Puedes iniciar tu servidor ahora.
pause
"""

bat_path = "/mnt/data/liberar_puerto_8765.bat"
with open(bat_path, "w", encoding="utf-8") as f:
    f.write(bat_code)

bat_path
