@echo off
chcp 65001 > /dev/null
cd /d "%~dp0\.."
echo.
echo ============================
echo  Knox PDF Send Test
echo ============================
echo.

set SERVER=http://10.246.9.74:80
set PDF_FILE=%~dp0\..\test\R3CW804XAD_analysis.pdf

echo [1] Register - chatroom + adaptive card
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "%SERVER%/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

timeout /t 2 /nobreak > /dev/null

echo [2] Send PDF file
powershell -NoProfile -Command ^
  "$body = @{ file_path = '%PDF_FILE%'; message = 'FA test PDF' } | ConvertTo-Json;" ^
  "try { $r = Invoke-WebRequest -Uri '%SERVER%/api/knox/send-file' -Method POST -ContentType 'application/json' -Body $body -UseBasicParsing; Write-Host $r.Content } catch { Write-Host 'Error:' $_.Exception.Message }"
echo.
echo.

echo Done! Check Knox Messenger.
echo.
pause
