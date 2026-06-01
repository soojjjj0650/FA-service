@echo off
chcp 65001 > nul
title 작업 스케줄러 등록

echo ====================================================
echo  매일 오전 9시 자동 로그인 스케줄 등록
echo ====================================================
echo.

:: 현재 스크립트 위치 기준으로 경로 설정
set "SCRIPT_DIR=%~dp0"
set "LOGIN_BAT=%SCRIPT_DIR%8_login_only.bat"

echo  등록할 배치 파일:
echo  %LOGIN_BAT%
echo.

:: 기존 작업 삭제 (있으면)
schtasks /delete /tn "통화품질분석서비스_자동로그인" /f > nul 2>&1

:: 작업 스케줄러 등록: 매일 오전 9:00
schtasks /create ^
  /tn "통화품질분석서비스_자동로그인" ^
  /tr "\"%LOGIN_BAT%\"" ^
  /sc daily ^
  /st 09:00 ^
  /ru "%USERNAME%" ^
  /rl limited ^
  /f

if errorlevel 1 (
    echo.
    echo [오류] 작업 스케줄러 등록 실패.
    echo        관리자 권한으로 실행해보세요.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  등록 완료!
echo  매일 오전 09:00에 자동으로 로그인 창이 열립니다.
echo  핸드폰에서 Bio 인증만 승인하면 됩니다.
echo.
echo  등록된 작업 확인:
echo  작업 스케줄러 열기 → 통화품질분석서비스_자동로그인
echo ====================================================
echo.
schtasks /query /tn "통화품질분석서비스_자동로그인" /fo list 2>nul
echo.
pause
