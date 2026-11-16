@echo off
title F5 Wardrobe Server + Cloudflare Tunnel
echo ========================================================
echo   Starting F5 Wardrobe Server and Cloudflare Tunnel
echo ========================================================

cd /d "%~dp0"

echo [1/2] Launching F5 Uvicorn Backend on port 8000...
start "F5 Backend Server" cmd /k "venv\Scripts\python.exe run_server.py"

timeout /t 3 /nobreak >nul

echo [2/2] Launching Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k "..\wardrobe\cloudflared.exe tunnel --url http://localhost:8000"

echo.
echo Both services have been started in separate windows!
echo Check the Cloudflare window for your public trycloudflare.com URL.
