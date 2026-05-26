@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Register
echo ============================
echo.

curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:8000/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

pause
