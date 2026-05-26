@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ============================
echo  Knox PDF Send Test
echo ============================
echo.

set PDF_PATH=%~dp0test\R3CW804XAD_analysis.pdf

echo [1] Register - chatroom + adaptive card
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

timeout /t 2 /nobreak > nul

echo [2] Send PDF file
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/send-file" ^
  -H "Content-Type: application/json" ^
  -d "{\"file_path\":\"%PDF_PATH:\=\\%\",\"message\":\"FA 분석 결과 PDF 테스트\"}"
echo.
echo.

echo Done! Check Knox Messenger.
echo.
pause
