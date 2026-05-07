@echo off
title NovellaxAI
echo ========================================
echo   NovellaxAI - CodeBuddy Gateway
echo   Proxy: :8090  ^|  Dashboard: :5173
echo ========================================
echo.

set "ROOT=%~dp0"

:: Kill existing instances
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8090.*LISTENING"') do (
    echo Killing proxy on port 8090 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173.*LISTENING"') do (
    echo Killing dashboard on port 5173 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

:: Check proxy binary exists
if not exist "%ROOT%proxy\novellaxai.exe" (
    echo ERROR: novellaxai.exe not found in %ROOT%proxy\
    echo Run: cd proxy ^&^& go build -o novellaxai.exe ./cmd/proxy
    pause
    exit /b 1
)

:: Start proxy in separate window
echo [1/2] Starting proxy...
start "NovellaxAI Proxy" cmd /k "cd /d "%ROOT%proxy" && novellaxai.exe --config config.yaml"

timeout /t 2 /nobreak >nul

:: Start dashboard in separate window
echo [2/2] Starting dashboard...
start "NovellaxAI Dashboard" cmd /k "cd /d "%ROOT%dashboard" && npm run dev"

echo.
echo ========================================
echo   Proxy:     http://localhost:8090
echo   Dashboard: http://localhost:5173
echo   API:       http://localhost:8090/v1/chat/completions
echo ========================================
echo.
echo Both services started in separate windows.
echo Close this window or press any key to exit.
echo.
pause
