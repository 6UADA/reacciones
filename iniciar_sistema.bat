@echo off
cd /d %~dp0
title Reaction Manager - Lanzador
echo.
echo ==========================================
echo    INICIANDO PANEL DE REACCIONES
echo ==========================================
echo.

:: 1. Intentar activar el entorno virtual si existe
if exist venv\Scripts\activate (
    echo [1/3] Activando entorno virtual...
    call venv\Scripts\activate
) else (
    echo [1/3] Entorno virtual no detectado, usando Python global...
)

:: 2. Iniciar el servidor Flask en una ventana nueva
echo [2/3] Iniciando servidor web (app.py)...
start "Reaction Manager - Server" pyth "python app.py"

:: 3. Esperar a que el servidor cargue antes de abrir el túnel
timeout /t 5 /nobreak > nul

:: 4. Iniciar el túnel de Cloudflare en una ventana nueva
echo [3/3] Iniciando Tunel de Cloudflare...
echo.
echo ==========================================
echo COPIA LA URL QUE APARECERA EN LA OTRA VENTANA
echo (Busca la linea que dice: https://...trycloudflare.com)
echo ==========================================
echo.
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5000"

echo.
echo Listo. No cierres las ventanas negras para mantener el sistema activo.
echo.
pause
