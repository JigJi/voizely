@echo off
REM Voizely nginx launcher
REM Uses voizely-specific config file at C:\deploy\voizely\nginx_conf\nginx.conf
REM nginx prefix is set to C:\nginx (where nginx.exe lives + where logs/ go)

if not exist C:\nginx\nginx.exe (
    echo [ERROR] nginx not found at C:\nginx\nginx.exe
    echo Download nginx for Windows from https://nginx.org/en/download.html
    echo Extract to C:\nginx so the path becomes C:\nginx\nginx.exe
    pause
    exit /b 1
)

if not exist C:\deploy\voizely\frontend\dist (
    echo [WARN] frontend\dist not built yet
    echo Run: cd C:\deploy\voizely\frontend ^&^& npm install ^&^& npm run build
)

cd /d C:\nginx
nginx.exe -p C:/nginx/ -c C:/deploy/voizely/nginx_conf/nginx.conf
