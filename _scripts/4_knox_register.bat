@echo off
cd /d "%~dp0.."
echo.
echo ============================
echo  Knox Messenger Start
echo ============================
echo.

echo Registering device + chatroom + sending SN input card...
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.
echo Done! Enter SN in Knox Messenger app to start FA analysis.
echo.
pause
