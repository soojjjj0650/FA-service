@echo off
cd /d "%~dp0.."
echo.
echo ============================
echo  Knox Direct Test
echo ============================
echo.

echo [1] Connection test (send text message)
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/test-message" ^
  -H "Content-Type: application/json"
echo.
echo.

echo [2] FA analysis direct test (manual SN input)
set /p INPUT_SN=Enter SN:
curl -s -w "\nHTTP %%{http_code}" ^
  -X POST "http://10.246.9.74:80/api/knox/send-analysis" ^
  -H "Content-Type: application/json" ^
  -d "{\"sn\":\"%INPUT_SN%\"}"
echo.
echo.
pause
