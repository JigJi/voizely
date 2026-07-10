@echo off
cd /d D:\0_product_dev\speech_text
echo Starting Speech-to-Text LOCAL Sovereign Worker

:: Trim audio to first N seconds for fast testing (900 = 15 min). Set 0 to process whole file.
set LOCAL_MAX_SEC=900

:loop
:: Kill any stale local_worker python before (re)starting, so we never end
:: up with two workers racing for the same pending transcription.
powershell -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -like '*local_worker*'} | ForEach-Object { Write-Host ('Killing stale worker PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 2 /nobreak >nul

python local_worker.py
echo.
echo [!] Local worker stopped. Restarting in 5 seconds... (Ctrl+C to exit)
timeout /t 5 /nobreak >nul
goto loop
