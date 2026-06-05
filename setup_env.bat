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
echo KNOX_MESSENGER_BASE_URL=https://openapi.samsung.net
echo KNOX_ACCESS_TOKEN=b0df5ab5-e432-37c4-8683-001f61150c49
echo KNOX_SYSTEM_ID=KCC10REST04505
echo KNOX_DEVICE_ID=211055033
echo KNOX_RECEIVER_USER_ID=929628016553234433
echo KNOX_MESSENGER_ENABLED=true
echo KNOX_RECEIVE_URL=http://10.246.9.74:80/pro/message
echo.
echo NETA_ENABLED=true
echo MOCK_MODE=false
echo AI_AGENT_ENABLED=false
echo.
echo MAIL_ENABLED=true
echo MAIL_USERNAME=sujin06.bae
echo MAIL_PASSWORD=tnwls1094!
echo MAIL_SCHEDULE_HOUR=6
echo MAIL_SCHEDULE_MINUTE=0
echo MAIL_HEADLESS=false
) > .env

echo .env created!
echo.
pause
