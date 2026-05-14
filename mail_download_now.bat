@echo off
chcp 65001 > nul
title FA 미결건 메일 다운로드 (수동 실행)

echo ============================================================
echo   FA 미결건 메일 첨부파일 수동 다운로드
echo ============================================================
echo.
echo  서버에 다운로드 요청 중...
echo.

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:80/api/mail/trigger' -Method POST -ContentType 'application/json' -Body '{}' -UseBasicParsing; Write-Host '요청 성공 (상태코드:' $r.StatusCode ')'; $json = $r.Content | ConvertFrom-Json; Write-Host '메시지:' $json.message } catch { Write-Host '오류:' $_.Exception.Message; Write-Host '서버가 실행 중인지 확인하세요.' }"

echo.
echo  다운로드는 백그라운드에서 실행됩니다.
echo  서버 로그에서 진행 상황을 확인하세요.
echo.
pause > nul
