@echo off
cd /d %~dp0

:: Activar entorno si existe
if exist venv\Scripts\activate (
    call venv\Scripts\activate
)

:: Iniciar Flask sin consola
start "" "C:\Users\GUADA\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe" app.py

:: Esperar 5 segundos
timeout /t 5 /nobreak > nul

:: Iniciar Cloudflare en segundo plano
start "" cloudflared tunnel --url http://localhost:5000
