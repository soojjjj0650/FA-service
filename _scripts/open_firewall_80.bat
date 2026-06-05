@echo off
chcp 65001 > nul
echo.
echo ============================
echo  Open Firewall Port 80
echo ============================
echo.

echo [1] Allow inbound TCP port 80 (all)
netsh advfirewall firewall add rule name="FA-Service-80" dir=in action=allow protocol=TCP localport=80
echo.

echo [2] Allow Knox Stage server IPs (112.106.197.161 / .162)
netsh advfirewall firewall add rule name="Knox-Stage-161" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.161
netsh advfirewall firewall add rule name="Knox-Stage-162" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.162
echo.

echo [3] Allow Knox Production RP server IPs (182.195.35.14/15/16)
netsh advfirewall firewall add rule name="Knox-Prod-RP14" dir=in action=allow protocol=TCP localport=80 remoteip=182.195.35.14
netsh advfirewall firewall add rule name="Knox-Prod-RP15" dir=in action=allow protocol=TCP localport=80 remoteip=182.195.35.15
netsh advfirewall firewall add rule name="Knox-Prod-RP16" dir=in action=allow protocol=TCP localport=80 remoteip=182.195.35.16
echo.

echo [4] Current firewall rules check (port 80 / Knox)
netsh advfirewall firewall show rule name=all | findstr /i "80\|Knox"
echo.

echo Done!
echo.
pause
