"""
Knox Messenger API 클라이언트
PDF 파일을 Knox Messenger를 통해 지정 사용자에게 전송합니다.

API 흐름:
  1. 파일 업로드 (POST /messenger/file/api/v2.0/file/v1sfile/{filename})
  2. 채팅방 생성 (POST /messenger/message/api/v2.0/message/createChatroomRequest)
  3. 메시지 전송 (POST /messenger/message/api/v2.0/message/chatRequest)
     - 메시지 본문은 AES256-CBC + Base64 암호화 필요
"""

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

# ─── AES256 암호화 헬퍼 ───────────────────────────────────────────────────────

def _aes256_encrypt(plaintext: str, key: bytes, iv: bytes) -> str:
    """AES256-CBC로 암호화 후 Base64 반환."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as sym_padding

        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")
    except ImportError:
        # cryptography 미설치 시 평문 Base64로 fallback (개발용)
        logger.warning("[Knox] cryptography 미설치 - 평문 Base64 사용 (운영 불가)")
        return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


# ─── Knox Messenger 클라이언트 ────────────────────────────────────────────────

class KnoxMessengerClient:
    """
    Knox Messenger API 클라이언트.

    설정:
      KNOX_MESSENGER_BASE_URL  : 서버 주소 (예: https://messenger.sec.samsung.net)
      KNOX_ACCESS_TOKEN        : Bearer 토큰 (Knox Portal에서 발급)
      KNOX_SYSTEM_ID           : System-ID 헤더값 (예: C60LD0001)
      KNOX_DEVICE_ID           : x-device-id 헤더값 (Knox Portal에서 발급)
      KNOX_RECEIVER_USER_ID    : 파일 받을 사용자 ID
    """

    def __init__(
        self,
        base_url: str,
        access_token: str,
        system_id: str,
        device_id: str,
        receiver_user_id: str,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.system_id = system_id
        self.device_id = device_id
        self.receiver_user_id = receiver_user_id
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
        }
        if self.device_id:
            h["x-device-id"] = self.device_id
            h["x-device-type"] = "relation"
        return h

    async def upload_file(self, file_path: str) -> str | None:
        """
        PDF 파일을 Knox Messenger 서버에 업로드합니다.
        반환: 파일 key/ID (메시지 전송 시 사용), 실패 시 None
        """
        filename = os.path.basename(file_path)
        url = f"{self.base_url}/messenger/file/api/v2.0/file/v1sfile/{filename}"

        if not os.path.exists(file_path):
            logger.error(f"[Knox] 업로드 파일 없음: {file_path}")
            return None

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            headers = self._headers()
            files = {"file": (filename, file_bytes, "application/pdf")}

            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.post(url, headers=headers, files=files)

            logger.info(f"[Knox] 파일 업로드 | status={resp.status_code} | body={resp.text[:300]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 파일 업로드 실패: {resp.status_code} {resp.text[:200]}")
                return None

            # 응답에서 파일 key 추출 (API 스펙에 따라 조정 필요)
            try:
                data = resp.json()
                file_key = (
                    data.get("fileKey")
                    or data.get("file_key")
                    or data.get("key")
                    or data.get("id")
                    or data.get("data", {}).get("fileKey")
                )
                if file_key:
                    logger.info(f"[Knox] 파일 업로드 완료: fileKey={file_key}")
                    return str(file_key)
            except Exception:
                pass

            # key를 못 파싱하면 응답 텍스트를 그대로 반환
            logger.warning(f"[Knox] 파일 key 파싱 불가 - 응답: {resp.text[:200]}")
            return resp.text.strip() or None

        except Exception as e:
            logger.error(f"[Knox] 파일 업로드 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def create_chatroom(self, title: str = "FA 분석 결과") -> str | None:
        """
        1:1 채팅방을 생성합니다.
        반환: chatroom_id, 실패 시 None
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/createChatroomRequest"
        payload = {
            "receiverUserId": self.receiver_user_id,
            "roomTitle": title,
            "roomType": "1to1",  # API 스펙에 따라 조정 필요
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.post(url, json=payload, headers=self._headers())

            logger.info(f"[Knox] 채팅방 생성 | status={resp.status_code} | body={resp.text[:300]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 채팅방 생성 실패: {resp.status_code} {resp.text[:200]}")
                return None

            try:
                data = resp.json()
                room_id = (
                    data.get("chatroomId")
                    or data.get("roomId")
                    or data.get("chatroom_id")
                    or data.get("data", {}).get("chatroomId")
                )
                if room_id:
                    logger.info(f"[Knox] 채팅방 생성 완료: roomId={room_id}")
                    return str(room_id)
            except Exception:
                pass

            return None

        except Exception as e:
            logger.error(f"[Knox] 채팅방 생성 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def get_encryption_keys(self) -> tuple[bytes, bytes] | None:
        """
        메시지 암호화용 AES256 키 + IV를 서버에서 조회합니다.
        반환: (key_bytes, iv_bytes) 또는 None
        """
        url = f"{self.base_url}/messenger/msgctx/api/v2.0/key/getkeys"
        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.get(url, headers=self._headers())

            if resp.status_code >= 400:
                logger.warning(f"[Knox] 암호화키 조회 실패: {resp.status_code} - 기본 키 사용")
                return None

            data = resp.json()
            key_b64 = data.get("aesKey") or data.get("key") or data.get("data", {}).get("aesKey")
            iv_b64 = data.get("aesIv") or data.get("iv") or data.get("data", {}).get("aesIv")

            if key_b64 and iv_b64:
                return base64.b64decode(key_b64), base64.b64decode(iv_b64)

            logger.warning(f"[Knox] 암호화키 파싱 불가: {resp.text[:200]}")
            return None

        except Exception as e:
            logger.warning(f"[Knox] 암호화키 조회 예외: {e}")
            return None

    async def send_file_message(
        self,
        chatroom_id: str,
        file_key: str,
        filename: str,
        message_text: str = "",
    ) -> bool:
        """
        채팅방에 파일과 텍스트 메시지를 전송합니다.
        반환: 성공 여부
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/chatRequest"

        # 메시지 암호화 시도
        encrypted_text = message_text
        keys = await self.get_encryption_keys()
        if keys and message_text:
            aes_key, aes_iv = keys
            encrypted_text = _aes256_encrypt(message_text, aes_key, aes_iv)

        payload = {
            "chatroomId": chatroom_id,
            "receiverUserId": self.receiver_user_id,
            "messageType": "file",
            "fileKey": file_key,
            "fileName": filename,
            "message": encrypted_text,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.post(url, json=payload, headers=self._headers())

            logger.info(f"[Knox] 메시지 전송 | status={resp.status_code} | body={resp.text[:300]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 메시지 전송 실패: {resp.status_code} {resp.text[:200]}")
                return False

            return True

        except Exception as e:
            logger.error(f"[Knox] 메시지 전송 예외: {type(e).__name__}: {e}", exc_info=True)
            return False


# ─── 메인 전송 함수 ───────────────────────────────────────────────────────────

async def send_pdf_via_knox(
    pdf_path: str,
    sn: str,
    base_url: str,
    access_token: str,
    system_id: str,
    device_id: str,
    receiver_user_id: str,
) -> bool:
    """
    PDF 파일을 Knox Messenger로 전송합니다.

    호출 전 확인 사항:
      - KNOX_MESSENGER_BASE_URL 설정 필요
      - KNOX_ACCESS_TOKEN 설정 필요
      - KNOX_DEVICE_ID 설정 필요 (Knox Portal에서 발급)
      - KNOX_RECEIVER_USER_ID 설정 필요 (받는 사람 ID)

    반환: 성공 여부
    """
    if not base_url:
        logger.warning("[Knox] KNOX_MESSENGER_BASE_URL 미설정 - 스킵")
        return False

    if not access_token:
        logger.warning("[Knox] KNOX_ACCESS_TOKEN 미설정 - 스킵")
        return False

    if not receiver_user_id:
        logger.warning("[Knox] KNOX_RECEIVER_USER_ID 미설정 - 스킵")
        return False

    if not os.path.exists(pdf_path):
        logger.error(f"[Knox] PDF 없음: {pdf_path}")
        return False

    client = KnoxMessengerClient(
        base_url=base_url,
        access_token=access_token,
        system_id=system_id,
        device_id=device_id,
        receiver_user_id=receiver_user_id,
    )

    filename = os.path.basename(pdf_path)
    logger.info(f"[Knox] PDF 전송 시작 | SN={sn} | 파일={filename}")

    # 1. 파일 업로드
    file_key = await client.upload_file(pdf_path)
    if not file_key:
        logger.error(f"[Knox] 파일 업로드 실패 - 전송 중단 (SN: {sn})")
        return False

    # 2. 채팅방 생성
    chatroom_id = await client.create_chatroom(title=f"FA 분석 결과 - {sn}")
    if not chatroom_id:
        logger.error(f"[Knox] 채팅방 생성 실패 - 전송 중단 (SN: {sn})")
        return False

    # 3. 파일 메시지 전송
    message = f"[FA 분석] SN: {sn}\n상세 분석 결과 PDF를 확인하세요."
    success = await client.send_file_message(
        chatroom_id=chatroom_id,
        file_key=file_key,
        filename=filename,
        message_text=message,
    )

    if success:
        logger.info(f"[Knox] PDF 전송 완료 | SN={sn}")
    else:
        logger.error(f"[Knox] PDF 전송 실패 | SN={sn}")

    return success
