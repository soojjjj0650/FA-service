"""
FA Chatbot Service - 서버 실행 진입점 (Windows 전용)

uvicorn 직접 실행 대신 이 파일을 사용하세요:
    python run.py
"""
import asyncio
import sys

# Playwright는 Windows에서 ProactorEventLoop가 필요
# uvicorn 시작 전에 반드시 설정해야 합니다
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,   # reload=True는 루프 정책을 무시하므로 False 사용
        loop="asyncio",
    )
