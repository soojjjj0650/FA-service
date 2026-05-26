@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Register
echo ============================
echo.

echo [1] Register (Device + Chatroom + Card)
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [2] Test Text Message
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/test-message" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [3] Send Analysis (SN 직접 입력해서 분석 + PDF 전송)
set /p INPUT_SN="SN 입력: "
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/send-analysis" ^
  -H "Content-Type: application/json" ^
  -d "{\"sn\":\"%INPUT_SN%\"}"
echo.
echo.

pause
