@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ============================
echo  Knox Messenger 시작
echo ============================
echo.

echo [1] Device 등록 + 대화방 생성 + SN 입력 카드 전송
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/register" ^
  -H "Content-Type: application/json"
echo.
echo.

echo 완료! Knox Messenger에서 SN을 입력하면 FA 분석이 자동으로 시작됩니다.
echo.
pause
