@echo off
chcp 65001 > nul
title FA Chatbot Full Test
setlocal enabledelayedexpansion

echo ============================================================
echo   FA Chatbot 전체 흐름 테스트
echo   (Webhook 조회접수 결과확인 Mock 카드 테스트)
echo ============================================================
echo.

set /p SERVER=Enter server URL (default: http://localhost:80):
if "!SERVER!"=="" set SERVER=http://localhost:80

echo.
echo [Server: !SERVER!]
echo.

:: 1. Server status
echo [1/5] 서버 상태 확인...
powershell -Command "try { $r = Invoke-WebRequest -Uri '!SERVER!/api/status' -Method GET -UseBasicParsing; $j = $r.Content | ConvertFrom-Json; Write-Host '  OK - browsers:' $j.active_browsers'/'$j.max_browsers '| session:' $j.session.status } catch { Write-Host '  [Error]' $_.Exception.Message }"
echo.

:: 2. Mock result card test
echo [2/5] Mock 결과 카드 테스트 (Superset 없이 카드 형식만 확인)...
powershell -Command "try { $r = Invoke-WebRequest -Uri '!SERVER!/api/test-result' -Method POST -ContentType 'application/json' -Body '{\"sn\":\"TEST-001\"}' -UseBasicParsing; $j = $r.Content | ConvertFrom-Json; Write-Host '  OK - type:' $j.type '| body count:' $j.body.Count } catch { Write-Host '  [Error]' $_.Exception.Message }"
echo.

:: 3. Webhook SN search request
echo [3/5] Webhook SN 조회 요청 (search_sn)...
set JOB_ID=
for /f "tokens=*" %%i in ('powershell -Command "try { $r = Invoke-WebRequest -Uri '!SERVER!/webhook' -Method POST -ContentType 'application/json' -Body '{\"action\":\"search_sn\",\"sn_value\":\"TEST-SN-001\",\"userId\":\"test_user\",\"chatRoomId\":\"test_room_001\"}' -UseBasicParsing; $j = $r.Content | ConvertFrom-Json; $actions = $j.actions; if ($actions) { $jobId = $actions[0].data.job_id; Write-Host $jobId } else { Write-Host 'NO_JOB_ID' } } catch { Write-Host 'ERROR:' $_.Exception.Message }"') do (
    set JOB_ID=%%i
)
echo   Job ID: !JOB_ID!
echo.

:: 4. Job list check
echo [4/5] Job 목록 확인 (/api/jobs)...
powershell -Command "try { $r = Invoke-WebRequest -Uri '!SERVER!/api/jobs' -Method GET -UseBasicParsing; $j = $r.Content | ConvertFrom-Json; Write-Host '  total jobs:' $j.total '| MOCK:' $j.mock_mode '| push_url_set:' $j.push_url_set; if ($j.jobs.Count -gt 0) { $latest = $j.jobs[0]; Write-Host '  latest: SN=' $latest.sn '| status=' $latest.status '| chatRoomId=' $latest.chatRoomId } } catch { Write-Host '  [Error]' $_.Exception.Message }"
echo.

:: 5. Result check
if not "!JOB_ID!"=="" if not "!JOB_ID!"=="NO_JOB_ID" (
    echo [5/5] 결과 확인 요청 (check_result - Job ID: !JOB_ID!)...
    powershell -Command "try { $r = Invoke-WebRequest -Uri '!SERVER!/webhook' -Method POST -ContentType 'application/json' -Body ('{\"action\":\"check_result\",\"job_id\":\"' + '!JOB_ID!' + '\",\"userId\":\"test_user\"}') -UseBasicParsing; $j = $r.Content | ConvertFrom-Json; Write-Host '  card type:' $j.type '| body count:' $j.body.Count } catch { Write-Host '  [Error]' $_.Exception.Message }"
) else (
    echo [5/5] Job ID 없음 - 결과 확인 스킵
)
echo.

echo ============================================================
echo   테스트 완료!
echo.
echo   체크리스트:
echo     1. 서버 상태 OK 확인
echo     2. Mock 카드 타입이 "AdaptiveCard" 인지 확인
echo     3. Webhook search_sn 응답에 job_id 포함 확인
echo     4. MOCK_MODE=true 설정 후 빠른 결과 테스트 가능
echo        (.env 파일에 MOCK_MODE=true 추가)
echo     5. CHATBOT_PUSH_URL 설정 시 결과 자동 push 활성화
echo ============================================================
echo.
pause
