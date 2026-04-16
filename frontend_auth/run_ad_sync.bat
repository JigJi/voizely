@echo off
cd /d C:\deploy\voizely\frontend_auth

:: --- Sanity checks (fail fast so Task Scheduler can detect) ---
if not exist venv\Scripts\python.exe (
    echo [FATAL] venv missing at %CD%\venv
    exit /b 1
)

if not exist .env (
    echo [FATAL] .env missing at %CD%\.env
    exit /b 1
)

echo [%DATE% %TIME%] Running AD sync job...
venv\Scripts\python.exe ad_sync_job.py
set RC=%ERRORLEVEL%
echo [%DATE% %TIME%] AD sync finished with exit code %RC%
exit /b %RC%
