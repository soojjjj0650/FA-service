@echo off
cd /d "%~dp0"
echo Disabling sleep mode (display timeout kept)...

powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

echo.
echo [OK] Sleep disabled. Display can still turn off.
echo.
pause
