@echo off
cd /d D:\0_product_dev\speech_text
echo Starting Speech-to-Text Gemini Worker

:loop
:: Kill any stale gemini_worker python before (re)starting, so we never end
:: up with two workers racing for the same pending transcription.
powershell -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -like '*gemini_worker*'} | ForEach-Object { Write-Host ('Killing stale worker PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 2 /nobreak >nul

python gemini_worker.py
echo.
echo [!] Worker stopped. Restarting in 5 seconds... (Ctrl+C to exit)
timeout /t 5 /nobreak >nul
goto loop
