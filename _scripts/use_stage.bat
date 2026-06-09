@echo off
cd /d "%~dp0\.."
echo Switching to STAGE environment...

(
echo HOST=0.0.0.0
echo PORT=80
echo LOG_LEVEL=INFO
echo BASE_URL=http://10.246.9.74
echo.
echo KNOX_MESSENGER_BASE_URL=https://openapi.stage.samsung.net
echo KNOX_ACCESS_TOKEN=c5e2b6bd-6f1f-3a35-b5a9-a88e2f0222de
echo KNOX_SYSTEM_ID=KCC10REST04505
echo KNOX_DEVICE_ID=21005797091
echo KNOX_RECEIVER_USER_ID=921475588965797889
echo KNOX_MESSENGER_ENABLED=true
echo KNOX_RECEIVE_URL=http://10.246.9.74:80/message
echo.
echo NETA_ENABLED=true
echo PREFETCH_ENABLED=false
echo LOGIN_AUTO_ENABLED=true
echo MOCK_MODE=false
echo AI_AGENT_ENABLED=false
echo.
echo MAIL_ENABLED=true
echo MAIL_USERNAME=sujin06.bae
echo MAIL_PASSWORD=tnwls1094!
echo MAIL_SCHEDULE_HOUR=18
echo MAIL_SCHEDULE_MINUTE=0
echo MAIL_HEADLESS=false
) > .env

if exist data\knox_chatroom_id_prod.txt del /Q data\knox_chatroom_id_prod.txt
if exist data\knox_chatroom_id.txt del /Q data\knox_chatroom_id.txt

echo Done. Current environment: STAGE
echo   Knox URL : https://openapi.stage.samsung.net
echo   Receive  : http://10.246.9.74:80/message
echo   Device ID: 21005797091
echo.
echo Restart the service to apply changes.
pause
