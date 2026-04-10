@echo off
cd /d D:\0_product_dev\speech_text
echo Starting Speech-to-Text Web Server on http://localhost:8800

:: Kill any python on port 8800
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8800.*LISTENING" 2^>nul') do (
    echo Killing old process %%a on port 8800...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:loop
python -m uvicorn app.main:app --host 127.0.0.1 --port 8800
echo.
echo [!] Server stopped. Restarting in 3 seconds... (Ctrl+C to exit)
timeout /t 3 /nobreak >nul
goto loop
