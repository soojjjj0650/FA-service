@echo off
echo Switching to PRODUCTION environment...
copy /Y .env.prod .env

echo Clearing stage Knox cache...
if exist data\knox_chatroom_id_stage.txt del /Q data\knox_chatroom_id_stage.txt
if exist data\knox_chatroom_id.txt del /Q data\knox_chatroom_id.txt

echo Done. Current environment: PRODUCTION
echo   Knox URL : https://openapi.samsung.net
echo   Receive  : http://10.246.9.74:80/pro/message
echo   Device ID: 211055033
echo.
echo Restart the service to apply changes.
pause
