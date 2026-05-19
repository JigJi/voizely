@echo off
cd /d C:\nginx

:: --- Sanity checks (fail fast so Task Scheduler can detect) ---
if not exist C:\nginx\nginx.exe (
    echo [FATAL] nginx not found at C:\nginx\nginx.exe
    echo Download from https://nginx.org/en/download.html and extract to C:\nginx\
    timeout /t 30 /nobreak >nul
    exit /b 1
)

if not exist C:\deploy\voizely\nginx_conf\nginx.conf (
    echo [FATAL] voizely nginx config missing
    timeout /t 30 /nobreak >nul
    exit /b 1
)

if not exist C:\deploy\voizely\frontend\dist\index.html (
    echo [WARN] frontend\dist\index.html not built ? run: cd C:\deploy\voizely\frontend ^&^& npm run build
)

echo Starting Voizely nginx on http://localhost:3100

:: --- Kill any old process on port 3100 (old voizely nginx instance) ---
:: Only port 3100 ? does NOT touch other nginx instances on different ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3100.*LISTENING" 2^>nul') do (
    echo Killing old process %%a on port 3100...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:loop
:: Remove stale pid from previous unclean shutdown (reboot, kill -9, etc.)
:: Without this, new nginx tries to signal a dead master and exits.
if exist C:\nginx\logs\nginx.pid del /f /q C:\nginx\logs\nginx.pid >nul 2>&1

C:\nginx\nginx.exe -p C:/nginx/ -c C:/deploy/voizely/nginx_conf/nginx.conf -g "daemon off;"
echo.
echo [!] nginx stopped. Restarting in 3 seconds... (Ctrl+C to exit)
timeout /t 3 /nobreak >nul
goto loop
