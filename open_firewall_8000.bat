@echo off
echo.
echo ============================
echo  Open Firewall Port 8000
echo ============================
echo.

netsh advfirewall firewall add rule name="FA-Service-8000" dir=in action=allow protocol=TCP localport=8000

echo.
echo Done!
pause
