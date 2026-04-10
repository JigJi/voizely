@echo off
cd /d D:\0_product_dev\speech_text
echo Starting Teams Recording Worker

:: Kill old worker: find python running teams_worker and kill it
powershell -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -like '*teams_worker*'} | ForEach-Object { Write-Host ('Killing old worker PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 2 /nobreak >nul

:loop
python teams_worker.py
echo.
echo [!] Teams worker cycle done. Next check in 60 seconds...
timeout /t 60 /nobreak >nul
goto loop
