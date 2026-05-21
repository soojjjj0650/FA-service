"""
Knox Teams 파일 전송 모듈
"""
import logging
import os
import httpx

logger = logging.getLogger(__name__)


async def send_html_to_teams(
    html_path: str,
    sn: str,
    api_url: str,
    api_key: str = "",
    channel_id: str = "",
) -> bool:
    """
    분석 HTML 파일을 Knox Teams 채널에 파일로 전송합니다.
    반환: 성공 여부
    """
    if not api_url:
        logger.warning("[Teams] TEAMS_FILE_API_URL 미설정 - 스킵")
        return False

    if not os.path.exists(html_path):
        logger.error(f"[Teams] HTML 파일 없음: {html_path}")
        return False

    filename = f"{sn}_analysis.html"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with open(html_path, "rb") as f:
            file_content = f.read()

        # multipart/form-data로 파일 전송 시도
        files = {"file": (filename, file_content, "text/html")}
        data = {"channelId": channel_id, "message": f"[FA 분석] {sn} 상세 분석 결과"}

        form_headers = {}
        if api_key:
            form_headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                api_url,
                files=files,
                data=data,
                headers=form_headers,
            )
            logger.info(f"[Teams] 전송 결과 | SN={sn} | status={resp.status_code} | body={resp.text[:200]}")
            return resp.status_code < 400

    except Exception as e:
        logger.error(f"[Teams] 전송 실패 (SN: {sn}): {type(e).__name__}: {e}", exc_info=True)
        return False
