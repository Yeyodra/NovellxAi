@echo off
title AI Proxy (CodeBuddy)
echo ========================================
echo   AI Proxy - CodeBuddy Gateway
echo   Port: 8090
echo ========================================
echo.

cd /d "C:\Users\Hanni\Documents\Projek\Github\aiproxy\proxy"

:: Kill existing instance if running
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8090.*LISTENING"') do (
    echo Killing existing process on port 8090 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo Starting proxy...
echo.
.\aiproxy.exe --config config.yaml
pause
