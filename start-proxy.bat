@echo off
title NovellaxAI (CodeBuddy)
echo ========================================
echo   NovellaxAI - CodeBuddy Gateway
echo   Port: 8090
echo ========================================
echo.

cd /d "%~dp0proxy"

:: Kill existing instance if running
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8090.*LISTENING"') do (
    echo Killing existing process on port 8090 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo Starting proxy...
echo.
.\novellaxai.exe --config config.yaml
pause
