@echo off
echo Switching to PRODUCTION environment...
copy /Y .env.prod .env
echo Done. Current environment: PRODUCTION
echo   Knox URL : https://openapi.samsung.net
echo   Receive  : http://10.246.9.74:80/pro/message
echo   Device ID: 211055033
pause
