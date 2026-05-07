@echo off
title NovellaxAI
echo ========================================
echo   NovellaxAI - CodeBuddy Gateway
echo   Proxy: :8090  |  Dashboard: :5173
echo ========================================
echo.

:: Kill existing instances
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8090.*LISTENING"') do (
    echo Killing proxy on port 8090 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173.*LISTENING"') do (
    echo Killing dashboard on port 5173 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

:: Start proxy in background
echo [1/2] Starting proxy...
cd /d "%~dp0proxy"
start /b "" novellaxai.exe --config config.yaml

:: Start dashboard
echo [2/2] Starting dashboard...
cd /d "%~dp0dashboard"
start /b "" cmd /c "npm run dev"

echo.
echo ========================================
echo   Proxy:     http://localhost:8090
echo   Dashboard: http://localhost:5173
echo   API:       http://localhost:8090/v1/chat/completions
echo ========================================
echo.
echo Press Ctrl+C to stop all services.
echo.

:: Keep window open, wait for Ctrl+C
:loop
timeout /t 3600 /nobreak >nul
goto loop
