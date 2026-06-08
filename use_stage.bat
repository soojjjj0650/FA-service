@echo off
echo Switching to STAGE environment...
copy /Y .env.stage .env

echo Clearing production Knox cache...
if exist data\knox_chatroom_id_prod.txt del /Q data\knox_chatroom_id_prod.txt
if exist data\knox_chatroom_id.txt del /Q data\knox_chatroom_id.txt

echo Done. Current environment: STAGE
echo   Knox URL : https://openapi.stage.samsung.net
echo   Receive  : http://10.246.9.74:80/message
echo   Device ID: 21005797091
echo.
echo Restart the service to apply changes.
pause
