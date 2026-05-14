@echo off
chcp 65001 > nul
title 메일 다운로드 이력 초기화

echo 다운로드 이력 파일을 삭제합니다...
del /f /q "%~dp0data\sessions\mail_downloaded_ids.json" 2>nul
echo 완료! 이제 mail_download_now.bat 을 실행하면 모든 메일을 다시 처리합니다.
echo.
pause > nul
