@echo off
cd /d "%~dp0"
echo Restoring sleep mode (default 30 min)...

powercfg /change standby-timeout-ac 30
powercfg /change hibernate-timeout-ac 60

echo.
echo [OK] Sleep mode restored. Standby: 30min, Hibernate: 60min.
echo.
pause
