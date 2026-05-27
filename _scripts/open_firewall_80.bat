@echo off
chcp 65001 > nul
echo.
echo ============================
echo  Knox Firewall 설정 (Port 80)
echo ============================
echo.

echo [1] 포트 80 인바운드 허용 (전체)
netsh advfirewall firewall add rule name="FA-Service-80" dir=in action=allow protocol=TCP localport=80
echo.

echo [2] Knox Stage 서버 IP 허용 (112.106.197.161 / .162)
netsh advfirewall firewall add rule name="Knox-Stage-161" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.161
netsh advfirewall firewall add rule name="Knox-Stage-162" dir=in action=allow protocol=TCP localport=80 remoteip=112.106.197.162
echo.

echo [3] 현재 포트 80 방화벽 규칙 확인
netsh advfirewall firewall show rule name=all | findstr /i "80\|Knox"
echo.

echo 완료! 서버 재시작 후 knox_start.bat 다시 실행하세요.
echo.
pause
