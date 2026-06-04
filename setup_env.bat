@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Creating .env ...

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
echo KNOX_RECEIVER_USER_ID=929628016553234433
echo KNOX_MESSENGER_ENABLED=true
echo KNOX_RECEIVE_URL=http://10.246.9.74:80/message
echo.
echo NETA_ENABLED=true
echo MOCK_MODE=false
echo AI_AGENT_ENABLED=false
echo.
echo MAIL_ENABLED=true
echo MAIL_USERNAME=sujin06.bae
echo MAIL_PASSWORD=tnwls1094!
echo MAIL_SCHEDULE_HOUR=17
echo MAIL_SCHEDULE_MINUTE=30
echo MAIL_HEADLESS=false
) > .env

echo .env created!
echo.
pause
