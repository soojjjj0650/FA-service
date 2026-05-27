@echo off
echo.
echo ============================
echo  Open Firewall Port 80
echo ============================
echo.

echo [1] Allow inbound TCP port 80
netsh advfirewall firewall add rule name="FA-Service-80" dir=in action=allow protocol=TCP localport=80
echo.

echo [2] Allow Knox Stage server IPs (112.106.197.161 / .162)
netsh advfirewall firewall add rule name="Knox-Stage-161" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.161
netsh advfirewall firewall add rule name="Knox-Stage-162" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.162
echo.

echo [3] Current firewall rules (port 80 / Knox)
netsh advfirewall firewall show rule name=all | findstr /i "80\|Knox"
echo.

echo Done! Restart server and re-run 4_knox_register.bat
echo.
pause
