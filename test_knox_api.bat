@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Messenger API Test
echo ============================
echo.

set STAGE_URL=https://openapi.stage.samsung.net
set STAGE_TOKEN=c5e2b6bd-6f1f-3a35-b5a9-a88e2f0222de
set SYSTEM_ID=KCC10REST04505
set DEVICE_ID=21005797091

echo [1] Public IP
curl -s http://checkip.amazonaws.com
echo.
echo.

echo [2] Device Register
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/contact/api/v2.0/device/o1/reg" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [3] File Server Key
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/msgctx/api/v2.0/key/getkeys" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "x-device-id: %DEVICE_ID%" ^
  -H "x-device-type: relation"
echo.
echo.

echo [4-A] User Lookup by knoxId (search)
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/contact/api/v2.0/user/search?knoxId=sujin06.bae" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "x-device-id: %DEVICE_ID%" ^
  -H "x-device-type: relation"
echo.
echo.

echo [4-B] User Lookup by userId param
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/contact/api/v2.0/user/search?userId=sujin06.bae" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "x-device-id: %DEVICE_ID%" ^
  -H "x-device-type: relation"
echo.
echo.

echo [4-C] User Info direct path
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/contact/api/v2.0/user/sujin06.bae" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "x-device-id: %DEVICE_ID%" ^
  -H "x-device-type: relation"
echo.
echo.

echo [4-D] Contacts search
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/messenger/contact/api/v2.0/contacts?knoxId=sujin06.bae" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "x-device-id: %DEVICE_ID%" ^
  -H "x-device-type: relation"
echo.
echo.

pause
