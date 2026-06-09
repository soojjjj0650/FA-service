@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================================
echo   FA Service - 자동 시작 해제 (작업 스케줄러)
echo ============================================================
echo.

set TASK_NAME=FA-Service-Chatbot

schtasks /delete /tn "%TASK_NAME%" /f

if %errorlevel% == 0 (
    echo.
    echo [완료] 자동 시작이 해제되었습니다.
) else (
    echo.
    echo [실패] 등록된 작업을 찾을 수 없거나 관리자 권한이 필요합니다.
    echo        이 파일을 오른쪽 클릭 ^> "관리자 권한으로 실행" 후 다시 시도하세요.
)

echo.
pause
