@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Messenger API Test
echo ============================
echo.

set STAGE_URL=https://openapi.stage.samsung.net
set STAGE_TOKEN=570623bc-a497-30f4-8de8-a80e199a6337
set SYSTEM_ID=KCC10BOT01508

echo [1] Public IP
curl -s http://checkip.amazonaws.com
echo.
echo.

echo [2] Device Register
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "%STAGE_URL%/v1/dp/device/register" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "Content-Type: application/json" ^
  -d "{\"deviceType\":\"SERVER\",\"deviceName\":\"FA-Service\"}"
echo.
echo.

echo [3] File Server Key
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/v1/dp/file/key" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%"
echo.
echo.

pause
