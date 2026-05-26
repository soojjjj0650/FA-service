@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ============================
echo  Knox FA 분석 요청
echo ============================
echo.

set /p INPUT_SN=Enter SN:

if "%INPUT_SN%"=="" (
    echo SN을 입력해주세요.
    pause
    exit /b
)

echo.
echo [%INPUT_SN%] 분석 요청 중...
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/send-analysis" ^
  -H "Content-Type: application/json" ^
  -d "{\"sn\":\"%INPUT_SN%\"}"
echo.
echo.
echo Knox Messenger에서 결과를 확인하세요.
echo.
pause
