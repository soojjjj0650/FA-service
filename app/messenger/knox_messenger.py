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
import gzip
import json
import logging
import os
import struct
import time
import asyncio
from functools import partial

import requests
import urllib3
from pathlib import Path
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# 캐시 파일 경로
_DEVICE_ID_CACHE   = Path(__file__).parent.parent.parent / "data" / "knox_device_id.txt"
_USER_ID_CACHE     = Path(__file__).parent.parent.parent / "data" / "knox_user_id.txt"
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


def _aes256_ecb_encrypt(plaintext: str, key: bytes) -> str:
    """평문 문자열 → AES256-ECB → Base64 인코딩 (IV 없음)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding

    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("ascii")


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


def _format_server_time(server_time: str) -> str:
    """
    getCurrentTime이 반환하는 serverTime을 AES 암호화 입력 포맷으로 변환.
    Unix ms (예: '1779784440310') → 'YYYYMMDDHHmmss' (예: '20260526173400')
    이미 날짜 포맷이면 그대로 반환.
    """
    s = server_time.strip()
    if s.isdigit() and len(s) >= 13:
        from datetime import datetime
        return datetime.utcfromtimestamp(int(s) / 1000).strftime('%Y%m%d%H%M%S')
    return s


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


def _load_cached_user_id() -> str:
    try:
        if _USER_ID_CACHE.exists():
            return _USER_ID_CACHE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _save_user_id(user_id: str) -> None:
    try:
        _USER_ID_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _USER_ID_CACHE.write_text(user_id, encoding="utf-8")
        logger.info(f"[Knox] User ID 저장 완료: {_USER_ID_CACHE}")
    except Exception as e:
        logger.warning(f"[Knox] User ID 저장 실패: {e}")


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
      KNOX_MESSENGER_BASE_URL  : 서버 주소 (예: https://openapi.stage.samsung.net)
      KNOX_ACCESS_TOKEN        : Bearer 토큰 (Knox Portal에서 발급)
      KNOX_SYSTEM_ID           : System-ID 헤더값 (예: KCC10BOT01508)
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
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.system_id = system_id
        self.device_id = device_id
        self.user_id = _load_cached_user_id()
        self.receiver_user_id = receiver_user_id
        self.timeout = timeout

    def _req(self, method: str, url: str, **kwargs) -> requests.Response:
        """동기 requests 호출 (SSL 검증 비활성화, 타임아웃 적용)."""
        # (connect_timeout, read_timeout) — Knox Stage 서버 응답이 느릴 수 있음
        kwargs.setdefault("timeout", (15, self.timeout))
        kwargs["verify"] = False
        return requests.request(method, url, **kwargs)

    async def _areq(self, method: str, url: str, **kwargs) -> requests.Response:
        """비동기 컨텍스트에서 requests 호출 (thread pool 사용)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._req, method, url, **kwargs))

    def _base_headers(self) -> dict:
        """Device ID 없이 기본 헤더만 반환 (등록 API 호출용)."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "User-Agent": "curl/7.81.0",
            "Accept": "*/*",
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
            resp = await self._areq("GET", url, headers=headers)

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
                if user_id:
                    self.user_id = str(user_id)
                    _save_user_id(self.user_id)
                return device_id

            logger.warning(f"[Knox] deviceServerID 없음 - 응답: {data}")
            return None

        except requests.exceptions.ConnectionError as e:
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

    async def get_file_server_time(self, word: str) -> tuple[str, str] | None:
        """
        파일 서버 암호화 Key 조회.
        GET /messenger/file/api/v2.0/file/v1/getCurrentTime?word={filename_or_path}

        반환: (serverTime, word_key) - 파일 업로드 헤더 암호화에 사용
        """
        url = f"{self.base_url}/messenger/file/api/v2.0/file/v1/getCurrentTime"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,
            "x-device-type": "relation",
        }
        try:
            resp = await self._areq("GET", url, params={"word": word}, headers=headers)

            logger.info(f"[Knox] 파일서버 Time 조회 | status={resp.status_code} | body={resp.text}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 파일서버 Time 조회 실패: {resp.status_code}")
                return None

            # parse_float=str prevents floating-point precision loss on serverTime
            import json as _json
            data = _json.loads(resp.text, parse_float=str)
            logger.info(f"[Knox] 파일서버 Time 파싱: serverTime={data.get('serverTime')!r} | word={data.get('word')!r}")

            server_time = str(data.get("serverTime") or data.get("server_time") or data.get("currentTime") or "")
            word_key    = str(data.get("word") or data.get("wordKey") or data.get("key") or "")

            if server_time and word_key:
                return server_time, word_key

            logger.warning(f"[Knox] 파일서버 Time 파싱 실패: {data}")
            return None

        except Exception as e:
            logger.error(f"[Knox] 파일서버 Time 조회 예외: {e}")
            return None

    async def upload_file(self, file_path: str) -> str | None:
        """
        파일을 Knox Messenger 파일 서버(v1s)에 업로드합니다.
        반환: (download_url, file_size) (성공), None (실패)
        """
        if not os.path.exists(file_path):
            logger.error(f"[Knox] 업로드 파일 없음: {file_path}")
            return None

        # 파일을 먼저 읽은 후 서버 시간 조회 (시간 만료 방지)
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            logger.error(f"[Knox] 파일 읽기 실패: {e}")
            return None

        import hashlib

        async def _try_upload() -> str | None:
            ext = os.path.splitext(file_path)[1]  # .pdf
            upload_filename = f"r{time.strftime('%Y%m%d%H%M%S')}{ext}"
            url = f"{self.base_url}/messenger/file/api/v2.0/file/v1s/file/{upload_filename}"

            # 파일 읽기 완료 후 바로 서버 시간 조회 → 암호화 → PUT
            time_result = await self.get_file_server_time(upload_filename)
            if not time_result:
                logger.error("[Knox] 파일서버 Time 조회 실패 - 업로드 중단")
                return None

            server_time, word_key = time_result
            formatted_time = _format_server_time(server_time)

            # word_key: 순수 base64이면 디코딩, 아닌 경우 UTF-8 바이트로 처리
            try:
                word_bytes = base64.b64decode(word_key, validate=True)
                logger.info(f"[Knox] word_key base64 디코딩 성공 | len={len(word_bytes)}")
            except Exception:
                word_bytes = word_key.encode("utf-8")
                logger.info(f"[Knox] word_key UTF-8 bytes 사용 | len={len(word_bytes)}")

            file_aes_key = word_bytes[:32] if len(word_bytes) >= 32 else hashlib.sha256(word_bytes).digest()
            file_aes_iv = b'\x00' * 16

            logger.info(f"[Knox] 업로드 암호화 파라미터 | server_time={server_time!r} | formatted={formatted_time!r} | word_key_prefix={word_key[:8]!r} | key_len={len(file_aes_key)}")

            try:
                enc_device_id   = _aes256_encrypt(self.device_id, file_aes_key, file_aes_iv)
                enc_device_type = _aes256_encrypt("relation",     file_aes_key, file_aes_iv)
                enc_server_time = _aes256_encrypt(formatted_time, file_aes_key, file_aes_iv)
            except Exception as e:
                logger.error(f"[Knox] 헤더 암호화 실패: {e}")
                return None

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "System-ID": self.system_id,
                "Content-Type": "binary/octet-stream",
                "Content-Length": str(len(file_bytes)),
                "filename":       upload_filename,
                "x-device-id":    enc_device_id,
                "x-device-type":  enc_device_type,
                "x-request-time": enc_server_time,
            }
            logger.info(f"[Knox] 업로드 요청(v1s) | url={url} | filename={upload_filename} | size={len(file_bytes)//1024}KB")

            resp = await self._areq("PUT", url, data=file_bytes, headers=headers)
            logger.info(f"[Knox] 파일 업로드(v1s) | status={resp.status_code} | body={resp.text[:500]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 파일 업로드 403 상세 | status={resp.status_code} | body={resp.text}")
                return None

            data = resp.json()
            download_url = data.get("download_url") or data.get("downloadUrl")
            if not download_url:
                logger.warning(f"[Knox] download_url 파싱 실패: {resp.text[:200]}")
                return None

            logger.info(f"[Knox] 파일 업로드 완료(v1s): {download_url}")
            return download_url

        try:
            result = await _try_upload()
            if result:
                return result, len(file_bytes)

            # 1회 재시도 (서버 시간 만료 대비)
            logger.warning(f"[Knox] 업로드 실패 → 2초 후 재시도: {os.path.basename(file_path)}")
            await asyncio.sleep(2)
            result = await _try_upload()
            if result:
                logger.info(f"[Knox] 재시도 업로드 성공: {os.path.basename(file_path)}")
                return result, len(file_bytes)

            return None

        except Exception as e:
            logger.error(f"[Knox] 파일 업로드 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def ensure_chatroom(self) -> str | None:
        """
        대화방 ID를 확보합니다.
        1) 캐시 파일에서 로드
        2) 없으면 create_chatroom() 호출하여 신규 생성
        """
        cached = _load_cached_chatroom_id()
        if cached:
            logger.info(f"[Knox] 캐시된 대화방 ID 사용: {cached}")
            return cached

        logger.info("[Knox] 대화방 없음 → 신규 생성")
        return await self.create_chatroom()

    async def create_chatroom(self) -> str | None:
        """
        대화방을 생성합니다.
        POST /messenger/message/api/v2.0/message/createChatroomRequest

        body (암호화 전):
        {"chatType": 2, "requestId": {timestamp_ms}, "receivers": [{userID}]}

        생성된 chatroomId는 캐시에 저장하여 재사용합니다.
        반환: chatroom_id, 실패 시 None
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/createChatroomRequest"

        request_id = int(time.time() * 1000)
        plain_payload = {
            "chatType": 1,
            "chatRoomName": "통화품질 분석서비스",
            "requestId": request_id,
            "receivers": [int(self.receiver_user_id)],
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            # 메시지 키로 payload 암호화
            msg_key = await self.get_message_key()
            logger.info(f"[Knox] 대화방 생성 payload(평문): {plain_payload}")
            if msg_key:
                logger.info(f"[Knox] 메시지 키 길이: {len(msg_key)} bytes")
                # 키가 32바이트면 IV를 별도 슬라이싱 불가 → 앞 16바이트 재사용
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                body = _encrypt_payload(plain_payload, msg_key[:32], iv)
                headers["Content-Type"] = "text/plain"
                resp = await self._areq("POST", url, data=body, headers=headers)
            else:
                logger.warning("[Knox] 메시지 키 없음 - 평문 전송 (테스트용)")
                resp = await self._areq("POST", url, json=plain_payload, headers=headers)

            logger.info(f"[Knox] 대화방 생성 | status={resp.status_code} | body={resp.text}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 대화방 생성 실패: {resp.status_code} | body={resp.text}")
                return None

            # 응답 복호화
            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                data = _decrypt_payload(resp.text.strip(), msg_key[:32], iv)
            else:
                data = resp.json()

            logger.info(f"[Knox] 대화방 생성 응답(복호화): {data}")

            chatroom_id = data.get("chatroomId")
            result_code = data.get("result", {}).get("code")

            if chatroom_id and result_code == 1000:
                chatroom_id = str(chatroom_id)
                logger.info(f"[Knox] 대화방 생성 완료: chatroomId={chatroom_id}")
                _save_chatroom_id(chatroom_id)
                return chatroom_id

            logger.warning(f"[Knox] 대화방 생성 실패 - code={result_code} data={data}")
            return None

        except Exception as e:
            logger.error(f"[Knox] 대화방 생성 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def get_message_key(self) -> bytes | None:
        """
        메시지 서버 암호화 Key 조회.
        GET /messenger/msgctx/api/v2.0/key/getkeys
        응답: {"key": "4cc~~~~~", "channelauthkey": "~~~~~"}

        반환: key bytes (Base64 디코딩), None (실패)
        """
        url = f"{self.base_url}/messenger/msgctx/api/v2.0/key/getkeys"
        headers = self._headers()
        headers["x-device-type"] = "relation"
        try:
            resp = await self._areq("GET", url, headers=headers)

            logger.info(f"[Knox] 메시지 키 조회 | status={resp.status_code} | body={resp.text[:200]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] 메시지 키 조회 실패: {resp.status_code}")
                return None

            data = resp.json()
            key_hex = data.get("key")
            if key_hex:
                key_bytes = bytes.fromhex(key_hex)
                logger.info(f"[Knox] 메시지 키 길이: {len(key_bytes)} bytes")
                return key_bytes

            logger.warning(f"[Knox] key 필드 없음: {data}")
            return None

        except Exception as e:
            logger.error(f"[Knox] 메시지 키 조회 예외: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def send_message(
        self,
        chatroom_id: str,
        message_text: str,
    ) -> bool:
        """
        채팅방에 텍스트 메시지를 전송합니다.
        POST /messenger/message/api/v2.0/message/chatRequest

        payload (암호화 전):
        {
            "requestId": {timestamp_ms},
            "chatroomId": {int},
            "chatMessageParams": [
                {
                    "msgId": {timestamp_ms},
                    "msgType": 0,
                    "chatMsg": {message_text},
                    "msgTtl": 7200
                }
            ]
        }

        반환: 성공 여부
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/chatRequest"

        request_id = int(time.time() * 1000)
        plain_payload = {
            "requestId": request_id,
            "chatroomId": int(chatroom_id),
            "chatMessageParams": [
                {
                    "msgId": request_id,
                    "msgType": 0,
                    "chatMsg": message_text,
                    "msgTtl": 7200,
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,  # 평문 그대로 전송
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            msg_key = await self.get_message_key()
            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                body = _encrypt_payload(plain_payload, msg_key[:32], iv)
                headers["Content-Type"] = "text/plain"
                resp = await self._areq("POST", url, data=body, headers=headers)
            else:
                logger.warning("[Knox] 메시지 키 없음 - 평문 전송 (테스트용)")
                resp = await self._areq("POST", url, json=plain_payload, headers=headers)

            logger.info(
                f"[Knox] 메시지 전송 | status={resp.status_code} "
                f"| body={resp.text[:300]}"
            )

            if resp.status_code >= 400:
                logger.error(f"[Knox] 메시지 전송 실패: {resp.status_code} {resp.text[:200]}")
                return False

            # 응답 복호화 및 결과 확인
            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                data = _decrypt_payload(resp.text.strip(), msg_key[:32], iv)
            else:
                data = resp.json()

            result_code = data.get("result", {}).get("code")
            if result_code == 1000:
                entries = data.get("processedMessageEntries", [])
                sent_time = entries[0].get("sentTime") if entries else None
                logger.info(f"[Knox] 메시지 전송 완료 | chatroomId={chatroom_id} | sentTime={sent_time}")
                return True

            logger.warning(f"[Knox] 메시지 전송 실패 - code={result_code} data={data}")
            return False

        except Exception as e:
            logger.error(f"[Knox] 메시지 전송 예외: {type(e).__name__}: {e}", exc_info=True)
            return False

    async def send_file_message(
        self,
        chatroom_id: str,
        download_url: str,
        filename: str,
        file_size: int = 0,
        message_text: str = "",
    ) -> bool:
        """
        채팅방에 파일을 msgType:1 (Media)로 전송합니다.
        chatMsg = download_url (Knox 파일서버 경로)
        Knox Messenger가 파일 첨부 UI로 렌더링합니다.

        POST /messenger/message/api/v2.0/message/chatRequest
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/chatRequest"

        # chatMsg = {"media":{...}} JSON 형식
        ext = os.path.splitext(filename)[1].lstrip(".").lower()  # "pdf", "zip"
        _IMG_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
        file_type = "image" if ext in _IMG_EXTS else "file"
        media_obj = {
            "media": {
                "extension": ext,
                "type": file_type,
                "filename": filename,
                "sender": self.user_id or self.device_id,
                "size": file_size,
                "url": download_url,
            }
        }
        chat_msg_json = json.dumps(media_obj, ensure_ascii=False)
        logger.info(f"[Knox] 파일 메시지 chatMsg(전송): {chat_msg_json[:200]}")

        request_id = int(time.time() * 1000)
        plain_payload = {
            "requestId": request_id,
            "chatroomId": int(chatroom_id),
            "chatMessageParams": [
                {
                    "msgId": request_id,
                    "msgType": 1,
                    "chatMsg": chat_msg_json,
                    "msgTtl": 7200,
                }
            ],
        }
        logger.info(f"[Knox] 파일 msgType=1 | ext={ext}")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            msg_key = await self.get_message_key()
            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                body = _encrypt_payload(plain_payload, msg_key[:32], iv)
                headers["Content-Type"] = "text/plain"
                resp = await self._areq("POST", url, data=body, headers=headers)
            else:
                logger.warning("[Knox] 메시지 키 없음 - 평문 전송 (테스트용)")
                resp = await self._areq("POST", url, json=plain_payload, headers=headers)

            logger.info(f"[Knox] 파일 메시지 전송 | status={resp.status_code} | body={resp.text[:300]}")

            if resp.status_code >= 400:
                logger.warning(f"[Knox] MEDIA 전송 실패({resp.status_code}) body={resp.text[:300]} - 텍스트로 fallback")
                fallback = f"[통화품질 분석] {filename}\n다운로드: {download_url}"
                return await self.send_message(chatroom_id, fallback)

            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                data = _decrypt_payload(resp.text.strip(), msg_key[:32], iv)
            else:
                data = resp.json()

            result_code = data.get("result", {}).get("code")
            if result_code == 1000:
                logger.info(f"[Knox] 파일 메시지 전송 완료 | chatroomId={chatroom_id} | file={filename}")
                return True

            logger.warning(f"[Knox] Media 전송 실패(code={result_code}) - 텍스트로 fallback")
            fallback = f"[통화품질 분석] {filename}\n다운로드: {download_url}"
            return await self.send_message(chatroom_id, fallback)

        except Exception as e:
            logger.error(f"[Knox] 파일 메시지 전송 예외: {type(e).__name__}: {e}", exc_info=True)
            return False


    async def send_adaptive_card(
        self,
        chatroom_id: str,
        card: dict,
    ) -> bool:
        """
        Adaptive Card를 채팅방에 전송합니다.
        msgType: 2 (Knox Messenger Adaptive Card)
        chatMsg: Adaptive Card JSON 문자열

        card 예시 (SN 입력 폼):
        {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.0",
            "body": [
                {"type": "TextBlock", "text": "통화품질 분석 요청"},
                {"type": "Input.Text", "id": "sn", "placeholder": "SN 입력"}
            ],
            "actions": [{
                "type": "Action.Submit",
                "title": "분석 요청",
                "data": {"requestUrl": "http://10.246.9.74:8000/message"}
            }]
        }
        """
        url = f"{self.base_url}/messenger/message/api/v2.0/message/chatRequest"

        request_id = int(time.time() * 1000)
        plain_payload = {
            "requestId": request_id,
            "chatroomId": int(chatroom_id),
            "chatMessageParams": [
                {
                    "msgId": request_id,
                    "msgType": 19,
                    "chatMsg": _build_adaptive_card_chatmsg(card),
                    "msgTtl": 7200,
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "System-ID": self.system_id,
            "x-device-id": self.device_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            msg_key = await self.get_message_key()
            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                body = _encrypt_payload(plain_payload, msg_key[:32], iv)
                headers["Content-Type"] = "text/plain"
                resp = await self._areq("POST", url, data=body, headers=headers)
            else:
                resp = await self._areq("POST", url, json=plain_payload, headers=headers)

            logger.info(f"[Knox] Adaptive Card 전송 | status={resp.status_code} | body={resp.text[:300]}")

            if resp.status_code >= 400:
                logger.error(f"[Knox] Adaptive Card 전송 실패: {resp.status_code}")
                return False

            if msg_key:
                iv = msg_key[32:48] if len(msg_key) >= 48 else msg_key[:16]
                data = _decrypt_payload(resp.text.strip(), msg_key[:32], iv)
            else:
                data = resp.json()

            result_code = data.get("result", {}).get("code")
            if result_code == 1000:
                logger.info(f"[Knox] Adaptive Card 전송 완료 | chatroomId={chatroom_id}")
                return True

            logger.warning(f"[Knox] Adaptive Card 전송 실패 - code={result_code}")
            return False

        except Exception as e:
            logger.error(f"[Knox] Adaptive Card 전송 예외: {type(e).__name__}: {e}", exc_info=True)
            return False


_COMPRESS_TAG = '<!--{"COMMAND":"SNDCL","SNDCL":{"KND":"CLDT","TYPE":"COMPRESS"}}-->'


def _build_adaptive_card_chatmsg(card: dict, compress: bool = False) -> str:
    """
    Knox Messenger Adaptive Card chatMsg 인코딩.
    1. card → JSON 문자열
    2. {"adaptiveCards": "<card_json>"} → JSON 문자열 (원문)
    3. (선택) gzip 압축 → 4바이트(원문 bit 길이) + 압축 bytes → base64 → COMPRESS 태그 추가
    """
    card_str = json.dumps(card, ensure_ascii=False)
    wrapper_str = json.dumps({"adaptiveCards": card_str}, ensure_ascii=False)

    if not compress:
        return wrapper_str

    raw_bytes = wrapper_str.encode("utf-8")
    bit_length = len(raw_bytes) * 8
    compressed = gzip.compress(raw_bytes)
    combined = struct.pack(">I", bit_length) + compressed
    encoded = base64.b64encode(combined).decode("ascii")
    return _COMPRESS_TAG + encoded


def build_sn_input_card(receive_url: str) -> dict:
    """SN 입력 안내 Adaptive Card (텍스트 직접 입력 방식)."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "통화품질 분석서비스",
                "size": "Medium",
                "weight": "Bolder",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": "분석할 단말기 SN을 채팅창에 입력해주세요.",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "예) R3CUFHDJF",
                "wrap": True,
                "isSubtle": True,
            },
        ],
    }


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
    ext = os.path.splitext(filename)[1].lower()
    file_type = "ZIP" if ext == ".zip" else "PDF"
    logger.info(f"[Knox] {file_type} 전송 시작 | SN={sn} | 파일={filename} | device_id={client.device_id}")

    # 1. 대화방 확보 (캐시 → 없으면 신규 생성)
    chatroom_id = await client.ensure_chatroom()
    if not chatroom_id:
        logger.error(f"[Knox] 대화방 확보 실패 - 전송 중단 (SN: {sn})")
        return False

    # 2. 파일 업로드
    upload_result = await client.upload_file(pdf_path)
    if not upload_result:
        logger.error(f"[Knox] 파일 업로드 실패 - 전송 중단 (SN: {sn})")
        return False
    download_url, file_size = upload_result

    # 3. 파일 메시지 전송
    ext = os.path.splitext(pdf_path)[1].lower()
    if ext == ".zip":
        message = f"[통화품질 분석] SN: {sn}\n분석 결과 파일({filename})을 다운로드하여 브라우저로 열어주세요."
    else:
        message = f"[통화품질 분석] SN: {sn}\n상세 분석 결과 파일({filename})을 확인하세요."
    success = await client.send_file_message(
        chatroom_id=chatroom_id,
        download_url=download_url,
        filename=filename,
        file_size=file_size,
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
