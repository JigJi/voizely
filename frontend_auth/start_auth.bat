@echo off
REM Voizely frontend_auth - local AD bind + JWT relay
REM Binds 127.0.0.1:8810 - must NOT be exposed externally

cd /d %~dp0

if not exist venv\Scripts\python.exe (
    echo [ERROR] venv not found. First-time setup:
    echo.
    echo   cd %~dp0
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist .env (
    echo [ERROR] .env not found. Copy .env.example to .env and fill in INTERNAL_API_KEY
    pause
    exit /b 1
)

venv\Scripts\python.exe -m uvicorn auth_app:app --host 127.0.0.1 --port 8810
