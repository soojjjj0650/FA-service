@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================================
echo   FA Service - 자동 시작 등록 (작업 스케줄러)
echo ============================================================
echo.

set TASK_NAME=FA-Service-Chatbot
set SCRIPT_PATH=%~dp0start_service_task.bat

echo 등록 정보:
echo   작업 이름 : %TASK_NAME%
echo   실행 파일 : %SCRIPT_PATH%
echo   실행 시점 : 로그인 시 자동 시작 (최소화)
echo.

schtasks /create /tn "%TASK_NAME%" /tr "cmd /c start /min \"통화품질 분석 서비스\" \"%SCRIPT_PATH%\"" /sc onlogon /rl highest /f

if %errorlevel% == 0 (
    echo.
    echo [완료] 다음 로그인부터 FA Service가 자동으로 시작됩니다.
    echo        지금 바로 시작하려면 start_service.bat을 실행하세요.
) else (
    echo.
    echo [실패] 이 파일을 오른쪽 클릭 ^> "관리자 권한으로 실행" 후 다시 시도하세요.
)

echo.
pause
