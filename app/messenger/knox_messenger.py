"""
Knox Messenger API 클라이언트
PDF 파일을 Knox Messenger를 통해 지정 사용자에게 전송합니다.

API 흐름:
  0. Device 등록   GET  /messenger/contact/api/v2.0/device/o1/reg
  1. 메시지키 조회  GET  /messenger/msgctx/api/v2.0/key/getkeys
  2. 파일 업로드   PUT  /messenger/file/api/v2.0/file/v1s/file/{filename}
  3. 대화방 생성   POST /messenger/message/api/v2.0/message/createChatroomRequest
  4. 메시지 발신   POST /messenger/message/api/v2.0/message/chatRequest
     - 메시지 API payload: 평문 JSON → AES256 → Base64
"""

import base64
import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# 캐시 파일 경로
_DEVICE_ID_CACHE   = Path(__file__).parent.parent.parent / "data" / "knox_device_id.txt"
_CHATROOM_ID_CACHE = Path(__file__).parent.parent.parent / "data" / "knox_chatroom_id.txt"


# ─── AES256 암호화/복호화 헬퍼 ───────────────────────────────────────────────

def _aes256_encrypt(plaintext: str, key: bytes, iv: bytes) -> str:
    """평문 문자열 → AES256-CBC → Base64 인코딩."""
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
        logger.warning("[Knox] cryptography 미설치 - 평문 Base64 사용 (운영 불가)")
        return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def _aes256_decrypt(ciphertext_b64: str, key: bytes, iv: bytes) -> dict:
    """Base64 → AES256-CBC 복호화 → dict 반환."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as sym_padding

        ciphertext = base64.b64decode(ciphertext_b64)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = sym_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        logger.error(f"[Knox] 복호화 실패: {e}")
        return {}


def _encrypt_payload(payload: dict, key: bytes, iv: bytes) -> str:
    """dict → JSON 직렬화 → AES256 → Base64 (메시지 API 공통)."""
    return _aes256_encrypt(json.dumps(payload, ensure_ascii=False), key, iv)


def _decrypt_payload(ciphertext_b64: str, key: bytes, iv: bytes) -> dict:
    """Base64 → AES256 복호화 → dict (메시지 API 공통)."""
    return _aes256_decrypt(ciphertext_b64, key, iv)


# ─── Device ID 캐시 관리 ─────────────────────────────────────────────────────

def _load_cached_device_id() -> str:
    """저장된 Device ID를 읽어옵니다."""
    try:
        if _DEVICE_ID_CACHE.exists():
            return _DEVICE_ID_CACHE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _save_device_id(device_id: str) -> None:
    """Device ID를 파일에 저장합니다."""
    try:
        _DEVICE_ID_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _DEVICE_ID_CACHE.write_text(device_id, encoding="utf-8")
        logger.info(f"[Knox] Device ID 저장 완료: {_DEVICE_ID_CACHE}")
    except Exception as e:
        logger.warning(f"[Knox] Device ID 저장 실패: {e}")


def _load_cached_chatroom_id() -> str:
    """저장된 대화방 ID를 읽어옵니다."""
    try:
        if _CHATROOM_ID_CACHE.exists():
            return _CHATROOM_ID_CACHE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _save_chatroom_id(chatroom_id: str) -> None:
    """대화방 ID를 파일에 저장합니다."""
    try:
        _CHATROOM_ID_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CHATROOM_ID_CACHE.write_text(chatroom_id, encoding="utf-8")
        logger.info(f"[Knox] 대화방 ID 저장 완료: {_CHATROOM_ID_CACHE}")
    except Exception as e:
        logger.warning(f"[Knox] 대화방 ID 저장 실패: {e}")


# ─── Knox Messenger 클라이언트 ────────────────────────────────────────────────

class KnoxMessengerClient:
    """
    Knox Messenger API 클라이언트.

    설정:
      KNOX_MESSENGER_BASE_URL  : 서버 주소 (예: https://messenger.sec.samsung.net)
      KNOX_ACCESS_TOKEN        : Bearer 토큰 (Knox Portal에서 발급)
      KNOX_SYSTEM_ID           : System-ID 헤더값 (예: C60LD0001)
      KNOX_DEVICE_ID           : x-device-id (비워두면 register_device()로 자동 획득)
      KNOX_RECEIVER_USER_ID    : 파일 받을 사용자 ID
    """

    def __init__(
        self,
        base_url: str,
        access_token: str,
        system_id: str,
        device_id: str = "",
        receiver_user_id: str = "",
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.system_id = system_id
        self.device_id = device_id
        self.receiver_user_id = receiver_user_id
        self.timeout = timeout

    def _base_headers(self) -> dict:
        """Device ID 없이 기본 헤더만 반환 (등록 API 호출용)."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
        }

    def _headers(self) -> dict:
        """Device ID 포함 전체 헤더 반환."""
        h = self._base_headers()
        if self.device_id:
            h["x-device-id"] = self.device_id
            h["x-device-type"] = "relation"
        return h

    async def register_device(self) -> str | None:
        """
        Device Registration API를 호출하여 Device ID를 획득합니다.

        GET /messenger/contact/api/v2.0/device/o1/reg
        응답: {"userID": 123456789, "deviceServerID": 1234556789, "newDevice": true}

        반환: deviceServerID (성공), None (실패)
        """
        url = f"{self.base_url}/messenger/contact/api/v2.0/device/o1/reg"
        logger.info(f"[Knox] Device 등록 요청: {url}")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-type": "relation",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.get(url, headers=headers)

            logger.info(
                f"[Knox] Device 등록 응답 | status={resp.status_code} "
                f"| body={resp.text[:500]}"
            )

            if resp.status_code >= 400:
                logger.error(
                    f"[Knox] Device 등록 실패: {resp.status_code} | "
                    f"body={resp.text[:300]}"
                )
                return None

            data = resp.json()
            logger.info(f"[Knox] Device 등록 응답 파싱: {data}")

            # deviceServerID가 실제 x-device-id로 사용되는 값
            device_server_id = data.get("deviceServerID")
            user_id = data.get("userID")
            new_device = data.get("newDevice", False)

            if device_server_id:
                device_id = str(device_server_id)
                logger.info(
                    f"[Knox] Device 등록 완료 | deviceServerID={device_id} "
                    f"| userID={user_id} | newDevice={new_device}"
                )
                self.device_id = device_id
                _save_device_id(device_id)
                return device_id

            logger.warning(f"[Knox] deviceServerID 없음 - 응답: {data}")
            return None
                or data.get("id")
                or data.get("devId")
                or data.get("data", {}).get("deviceId")
                or data.get("data", {}).get("device_id")
                or data.get("result", {}).get("deviceId")
            )

        except httpx.ConnectError as e:
            logger.error(f"[Knox] 서버 연결 실패 ({self.base_url}): {e}")
            return None
        except Exception as e:
            logger.error(f"[Knox] Device 등록 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def ensure_device_id(self) -> bool:
        """
        Device ID가 없으면 자동으로 등록합니다.
        1) config에서 설정된 값 사용
        2) 캐시 파일에서 로드
        3) 없으면 register_device() 호출

        반환: device_id 확보 여부
        """
        if self.device_id:
            return True

        # 캐시 파일 확인
        cached = _load_cached_device_id()
        if cached:
            logger.info(f"[Knox] 캐시된 Device ID 사용: {cached}")
            self.device_id = cached
            return True

        # 신규 등록
        logger.info("[Knox] Device ID 없음 → 자동 등록 시도")
        device_id = await self.register_device()
        return device_id is not None

    async def upload_file(self, file_path: str, aes_key: bytes = b"", aes_iv: bytes = b"") -> str | None:
        """
        파일을 Knox Messenger 파일 서버에 업로드합니다.
        PUT /messenger/file/api/v2.0/file/v1s/file/{filename}

        파일명 규칙: "r" + YYYYMMDDHHmmss + 확장자 (예: r20240521143022.pdf)
        반환: download_url (성공), None (실패)
        """
        import time as _time

        if not os.path.exists(file_path):
            logger.error(f"[Knox] 업로드 파일 없음: {file_path}")
            return None

        ext = os.path.splitext(file_path)[1]  # .pdf
        timestamp = _time.strftime("%Y%m%d%H%M%S")
        upload_filename = f"r{timestamp}{ext}"
        url = f"{self.base_url}/messenger/file/api/v2.0/file/v1s/file/{upload_filename}"

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            file_size = len(file_bytes)

            # 헤더 구성
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "System-ID": self.system_id,
                "Content-Length": str(file_size),
                "Content-Type": "binary/octet-stream",
                "filename": upload_filename,
            }

            # x-device-id, x-device-type, x-request-time: AES256 암호화 필요
            # 암호화 키가 있는 경우에만 암호화, 없으면 평문 전송 (테스트용)
            if aes_key and aes_iv and self.device_id:
                headers["x-device-id"]   = _aes256_encrypt(self.device_id, aes_key, aes_iv)
                headers["x-device-type"] = _aes256_encrypt("relation", aes_key, aes_iv)
                headers["x-request-time"] = _aes256_encrypt(str(int(_time.time() * 1000)), aes_key, aes_iv)
            else:
                # 암호화 키 미확보 시 평문 (추후 파일서버 암호화 Key API 연동 후 교체)
                headers["x-device-id"]   = self.device_id
                headers["x-device-type"] = "relation"
                headers["x-request-time"] = str(int(_time.time() * 1000))

            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.put(url, content=file_bytes, headers=headers)

            logger.info(
                f"[Knox] 파일 업로드 | status={resp.status_code} "
                f"| url={url} | body={resp.text[:300]}"
            )

            if resp.status_code >= 400:
                logger.error(f"[Knox] 파일 업로드 실패: {resp.status_code} {resp.text[:200]}")
                return None

            data = resp.json()
            download_url = data.get("download_url") or data.get("downloadUrl")
            if download_url:
                logger.info(f"[Knox] 파일 업로드 완료: {download_url}")
                return download_url

            logger.warning(f"[Knox] download_url 파싱 실패: {resp.text[:200]}")
            return None

        except Exception as e:
            logger.error(f"[Knox] 파일 업로드 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def ensure_chatroom(self) -> str | None:
        """
        대화방 ID를 확보합니다.
        1) 캐시 파일에서 로드
        2) 없으면 create_chatroom() 호출하여 신규 생성

        반환: chatroom_id, 실패 시 None
        """
        cached = _load_cached_chatroom_id()
        if cached:
            logger.info(f"[Knox] 캐시된 대화방 ID 사용: {cached}")
            return cached

        logger.info("[Knox] 대화방 없음 → 신규 생성")
        return await self.create_chatroom()

    async def create_chatroom(self, title: str = "FA 분석 결과") -> str | None:
        """
        대화방을 생성합니다. 생성된 ID는 캐시에 저장하여 재사용합니다.
        반환: chatroom_id, 실패 시 None
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/createChatroomRequest"
        payload = {
            "receiverUserId": self.receiver_user_id,
            "roomTitle": title,
            "roomType": "1to1",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.post(url, json=payload, headers=self._headers())

            logger.info(
                f"[Knox] 채팅방 생성 | status={resp.status_code} "
                f"| body={resp.text[:300]}"
            )

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
                    room_id = str(room_id)
                    logger.info(f"[Knox] 채팅방 생성 완료: roomId={room_id}")
                    _save_chatroom_id(room_id)
                    return room_id
            except Exception:
                pass

            return None

        except Exception as e:
            logger.error(f"[Knox] 채팅방 생성 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def get_message_key(self) -> bytes | None:
        """
        메시지 서버 암호화 Key 조회.
        GET /messenger/msgctx/api/v2.0/key/getkeys
        응답: {"key": "4cc~~~~~", "channelauthkey": "~~~~~"}

        반환: key bytes (Base64 디코딩), None (실패)
        """
        url = f"{self.base_url}/messenger/msgctx/api/v2.0/key/getkeys"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,
            "x-device-type": "relation",
        }
        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.get(url, headers=headers)

            logger.info(f"[Knox] 메시지 키 조회 | status={resp.status_code} | body={resp.text[:200]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 메시지 키 조회 실패: {resp.status_code}")
                return None

            data = resp.json()
            key_b64 = data.get("key")
            if key_b64:
                return base64.b64decode(key_b64)

            logger.warning(f"[Knox] key 필드 없음: {data}")
            return None

        except Exception as e:
            logger.error(f"[Knox] 메시지 키 조회 예외: {e}")
            return None

    async def send_file_message(
        self,
        chatroom_id: str,
        download_url: str,
        filename: str,
        message_text: str = "",
    ) -> bool:
        """채팅방에 파일 메시지를 전송합니다. payload는 AES256→Base64 암호화."""
        url = f"{self.base_url}/messenger/message/api/v2.0/message/chatRequest"

        plain_payload = {
            "chatroomId": chatroom_id,
            "receiverUserId": self.receiver_user_id,
            "messageType": "file",
            "downloadUrl": download_url,
            "fileName": filename,
            "message": message_text,
        }

        # 메시지 키 조회 → payload 암호화
        msg_key = await self.get_message_key()
        if msg_key:
            iv = msg_key[:16]  # 앞 16바이트를 IV로 사용
            encrypted = _encrypt_payload(plain_payload, msg_key, iv)
            body = encrypted  # 암호화된 문자열을 body로 전송
            headers = {**self._headers(), "Content-Type": "text/plain"}
        else:
            logger.warning("[Knox] 메시지 키 없음 - 평문 전송 (테스트용)")
            body = None
            headers = self._headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                if body:
                    resp = await client.post(url, content=body, headers=headers)
                else:
                    resp = await client.post(url, json=plain_payload, headers=headers)

            logger.info(
                f"[Knox] 메시지 전송 | status={resp.status_code} "
                f"| body={resp.text[:300]}"
            )

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
    device_id가 비어있으면 register_device()를 호출해 자동 획득합니다.

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

    # Device ID 확보 (config → 캐시 → 자동 등록)
    if not await client.ensure_device_id():
        logger.error(f"[Knox] Device ID 확보 실패 - 전송 중단 (SN: {sn})")
        return False

    filename = os.path.basename(pdf_path)
    logger.info(f"[Knox] PDF 전송 시작 | SN={sn} | 파일={filename} | device_id={client.device_id}")

    # 1. 대화방 확보 (캐시 → 없으면 신규 생성)
    chatroom_id = await client.ensure_chatroom()
    if not chatroom_id:
        logger.error(f"[Knox] 대화방 확보 실패 - 전송 중단 (SN: {sn})")
        return False

    # 2. 파일 업로드
    download_url = await client.upload_file(pdf_path)
    if not download_url:
        logger.error(f"[Knox] 파일 업로드 실패 - 전송 중단 (SN: {sn})")
        return False

    # 3. 파일 메시지 전송
    message = f"[FA 분석] SN: {sn}\n상세 분석 결과 PDF를 확인하세요."
    success = await client.send_file_message(
        chatroom_id=chatroom_id,
        download_url=download_url,
        filename=filename,
        message_text=message,
    )

    if success:
        logger.info(f"[Knox] PDF 전송 완료 | SN={sn}")
    else:
        logger.error(f"[Knox] PDF 전송 실패 | SN={sn}")

    return success


async def register_device_only(
    base_url: str,
    access_token: str,
    system_id: str,
) -> str | None:
    """
    Device ID만 등록하고 반환합니다.
    서버 시작 시 또는 /api/knox/register 엔드포인트에서 수동 호출용.

    반환: device_id (성공), None (실패)
    """
    client = KnoxMessengerClient(
        base_url=base_url,
        access_token=access_token,
        system_id=system_id,
    )
    return await client.register_device()
