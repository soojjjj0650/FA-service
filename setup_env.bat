@echo off
cd /d "%~dp0"

echo KNOX_MESSENGER_BASE_URL=https://openapi.stage.samsung.net> .env
echo KNOX_ACCESS_TOKEN=c5e2b6bd-6f1f-3a35-b5a9-a88e2f0222de>> .env
echo KNOX_SYSTEM_ID=KCC10REST04505>> .env
echo KNOX_DEVICE_ID=21005797091>> .env
echo KNOX_RECEIVER_USER_ID=921475588965797889>> .env
echo KNOX_MESSENGER_ENABLED=true>> .env
echo HOST=0.0.0.0>> .env
echo PORT=8000>> .env
echo LOG_LEVEL=INFO>> .env

echo .env created!
pause
