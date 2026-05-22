@echo off
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Messenger API 연결 테스트
echo ============================
echo.

set STAGE_URL=https://openapi.stage.samsung.net
set STAGE_TOKEN=570623bc-a497-30f4-8de8-a80e199a6337
set SYSTEM_ID=KCC10BOT01508

echo [1] 내 서버 공인 IP 확인
curl -s http://checkip.amazonaws.com
echo.
echo.

echo [2] Knox Stage API - Device 등록 테스트
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "%STAGE_URL%/v1/dp/device/register" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%" ^
  -H "Content-Type: application/json" ^
  -d "{\"deviceType\":\"SERVER\",\"deviceName\":\"FA-Service\"}"
echo.
echo.

echo [3] Knox Stage API - File Server Key 조회 테스트
curl -s -w "\nHTTP %%{http_code}" ^
  -X GET "%STAGE_URL%/v1/dp/file/key" ^
  -H "Authorization: Bearer %STAGE_TOKEN%" ^
  -H "System-Id: %SYSTEM_ID%"
echo.
echo.

pause
