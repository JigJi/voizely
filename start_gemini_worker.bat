@echo off
cd /d D:\0_product_dev\speech_text
echo Starting Speech-to-Text Gemini Worker

:: Kill old worker: find python running gemini_worker and kill it
powershell -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -like '*gemini_worker*'} | ForEach-Object { Write-Host ('Killing old worker PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 2 /nobreak >nul

:loop
python gemini_worker.py
echo.
echo [!] Worker stopped. Restarting in 5 seconds... (Ctrl+C to exit)
timeout /t 5 /nobreak >nul
goto loop
