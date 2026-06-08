@echo off
echo Switching to STAGE environment...
copy /Y .env.stage .env
echo Done. Current environment: STAGE
echo   Knox URL : https://openapi.stage.samsung.net
echo   Receive  : http://10.246.9.74:80/message
echo   Device ID: 21005797091
pause
