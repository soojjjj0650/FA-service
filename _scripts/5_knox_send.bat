@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo.
echo ============================
echo  Knox FA 분석 직접 테스트
echo ============================
echo.

echo [1] 연결 테스트 (텍스트 메시지 전송)
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/test-message" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [2] FA 분석 직접 실행 (SN 수기 입력)
set /p INPUT_SN=SN 입력:
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/send-analysis" ^
  -H "Content-Type: application/json" ^
  -d "{\"sn\":\"%INPUT_SN%\"}"
echo.
echo.
pause
