@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Register
echo ============================
echo.

echo [1] Register (Device + Chatroom + Card)
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:8000/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [2] Test Text Message
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:8000/api/knox/test-message" ^
  -H "Content-Type: application/json"
echo.
echo.

pause
