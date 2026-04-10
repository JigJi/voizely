@echo off
cd /d C:\deploy\voizely\frontend_auth

:: --- Sanity checks (fail fast so Task Scheduler can detect) ---
if not exist venv\Scripts\python.exe (
    echo [FATAL] venv missing at %CD%\venv
    echo Run setup once:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    timeout /t 30 /nobreak >nul
    exit /b 1
)

if not exist .env (
    echo [FATAL] .env missing at %CD%\.env
    echo Copy .env.example to .env and fill in INTERNAL_API_KEY
    timeout /t 30 /nobreak >nul
    exit /b 1
)

echo Starting Voizely frontend_auth on http://127.0.0.1:8810

:: --- Kill any old process on port 8810 ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8810.*LISTENING" 2^>nul') do (
    echo Killing old process %%a on port 8810...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:loop
venv\Scripts\python.exe -m uvicorn auth_app:app --host 127.0.0.1 --port 8810
echo.
echo [!] frontend_auth stopped. Restarting in 3 seconds... (Ctrl+C to exit)
timeout /t 3 /nobreak >nul
goto loop
