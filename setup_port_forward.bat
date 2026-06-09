@echo off
echo.
echo ============================
echo  Port Forward 8000 -> 80
echo ============================
echo.

netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=80 connectaddress=127.0.0.1

echo.
echo [Check]
netsh interface portproxy show all

echo.
echo Done! Port 8000 -> 80 forwarding active.
pause
