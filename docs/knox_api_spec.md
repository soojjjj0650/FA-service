# Knox Messenger API 스펙 정리

## 공통 정보

| 항목 | 값 |
|------|-----|
| BASE_URL | `https://openapi.stage.samsung.net` (stage) |
| Authorization | `Bearer {KNOX_ACCESS_TOKEN}` |
| System-ID | `{KNOX_SYSTEM_ID}` (예: KCC10BOT01508) |

---

## 1. Device 등록

**GET** `/messenger/contact/api/v2.0/device/o1/reg`

### Headers
| 키 | 값 |
|----|-----|
| Authorization | Bearer {access_token} |
| System-ID | {system_id} |
| x-device-type | relation |
| Content-Type | application/json |
| Accept | application/json |

### Response Body
```json
{
  "userID": 21005780439,
  "deviceServerID": 1234556789,
  "newDevice": true
}
```

> - `userID` → 파일 메시지 sender 필드에 사용
> - `deviceServerID` → 이후 모든 API의 `x-device-id` 헤더에 사용

---

## 2. 메시지 암호화 Key 조회 (getkeys)

**GET** `/messenger/msgctx/api/v2.0/key/getkeys`

### Headers
| 키 | 값 |
|----|-----|
| Authorization | Bearer {access_token} |
| System-ID | {system_id} |
| x-device-id | {deviceServerID} |
| x-device-type | relation |

### Response Body
```json
{
  "key": "4cc8f1a2b3...(hex string, 96자)",
  "channelauthkey": "..."
}
```

> - `key` hex 디코딩 → bytes
> - AES Key = key_bytes[:32], AES IV = key_bytes[32:48]
> - 이후 chatRequest body 암호화에 사용

---

## 3. 파일 서버 Time/Key 조회 (getCurrentTime)

**GET** `/messenger/file/api/v2.0/file/v1/getCurrentTime?word={filename}`

### Headers
| 키 | 값 |
|----|-----|
| Authorization | Bearer {access_token} |
| System-ID | {system_id} |
| x-device-id | {deviceServerID} |
| x-device-type | relation |

### Query Parameter
| 파라미터 | 값 |
|---------|-----|
| word | 업로드할 파일명 (예: r20260526173400.pdf) |

### Response Body
```json
{
  "serverTime": 1779784440310,
  "word": "!2#4%6&8(0r20260526173400.pdf1@3"
}
```

> - `word` 값이 파일 업로드 헤더 암호화 키
> - AES Key = word[:32] bytes, AES IV = 0x00 * 16 (zeros)

---

## 4. 파일 업로드

**PUT** `/messenger/file/api/v2.0/file/v1s/file/{filename}`

> 파일명 규칙: `r` + YYYYMMDDHHmmss + 확장자  
> 예) `r20260526173400.pdf`

### Headers
| 키 | 값 | 비고 |
|----|-----|------|
| Authorization | Bearer {access_token} | 평문 |
| System-ID | {system_id} | 평문 |
| Content-Type | binary/octet-stream | |
| Content-Length | {파일 크기 bytes} | |
| filename | r20260526173400.pdf | 평문, Mandatory |
| x-device-id | AES256(deviceServerID) | CBC, key=word[:32], IV=zeros |
| x-device-type | AES256("relation") | CBC, key=word[:32], IV=zeros |
| x-request-time | AES256(serverTime) | CBC, key=word[:32], IV=zeros |

> AES256-CBC: PKCS7 padding, key=word[:32] bytes, IV=b'\x00'*16, Base64 인코딩

### Request Body
파일 binary data

### Response Body
```json
{
  "download_url": "https://sqaproxy.stage.samsung.net/file/v1s/file/TOKEN"
}
```

---

## 5. 대화방 생성

**POST** `/messenger/message/api/v2.0/message/createChatroomRequest`

### Headers
| 키 | 값 |
|----|-----|
| Authorization | Bearer {access_token} |
| System-ID | {system_id} |
| x-device-id | {deviceServerID} |
| Content-Type | text/plain |

### Request Body (암호화 전 JSON)
```json
{
  "chatType": 1,
  "requestId": 1523982989389,
  "receivers": [21005780439]
}
```

> body = AES256-CBC(JSON) → Base64  
> key = getkeys key_bytes[:32], IV = key_bytes[32:48]

### Response Body (복호화 후 JSON)
```json
{
  "chatroomId": 99934234242,
  "result": { "code": 1000 }
}
```

---

## 6. 텍스트 메시지 전송 (chatRequest)

**POST** `/messenger/message/api/v2.0/message/chatRequest`

### Headers
| 키 | 값 |
|----|-----|
| Authorization | Bearer {access_token} |
| System-ID | {system_id} |
| x-device-id | {deviceServerID} |
| Content-Type | text/plain |

### Request Body (암호화 전 JSON)
```json
{
  "requestId": 1523982989389,
  "chatroomId": 99934234242,
  "chatMessageParams": [
    {
      "msgId": 1523982989389,
      "msgType": 0,
      "chatMsg": "메시지 내용",
      "msgTtl": 7200
    }
  ]
}
```

### msgType 목록
| 값 | 설명 |
|----|------|
| 0 | 일반 텍스트 |
| 1 | MEDIA (이미지/파일 첨부) |
| 19 | Adaptive Card |

---

## 7. 파일 메시지 전송 (chatRequest - MEDIA)

**POST** `/messenger/message/api/v2.0/message/chatRequest`

Headers 동일 (6번과 같음)

### Request Body (암호화 전 JSON)
```json
{
  "requestId": 1523982989389,
  "chatroomId": 99934234242,
  "chatMessageParams": [
    {
      "msgId": 1523982989389,
      "msgType": 1,
      "chatMsg": "{\"media\":{\"extention\":\"pdf\",\"type\":\"PDF\",\"filename\":\"report.pdf\",\"sender\":\"21005780439\",\"size\":5424412,\"url\":\"https://sqaproxy.stage.samsung.net/file/v1s/file/TOKEN\"}}",
      "msgTtl": 7200
    }
  ]
}
```

### chatMsg 구조 (msgType=1, JSON string)
```json
{
  "media": {
    "extention": "pdf",
    "type": "PDF",
    "filename": "report.pdf",
    "sender": "21005780439",
    "size": 5424412,
    "url": "https://sqaproxy.stage.samsung.net/file/v1s/file/TOKEN"
  }
}
```

| 필드 | 설명 |
|------|------|
| extention | 파일 확장자 소문자 (pdf, zip, png ...) |
| type | PDF / ZIP / image 등 |
| filename | 원본 파일명 |
| sender | 발신자 userID (device 등록 시 획득) |
| size | 파일 크기 (bytes) |
| url | 파일 업로드 후 받은 download_url |

---

## 암호화 요약

| 용도 | 알고리즘 | Key | IV |
|------|---------|-----|-----|
| 파일 업로드 헤더 | AES-256-CBC | getCurrentTime `word`[:32] bytes | 0x00 * 16 |
| 메시지 body | AES-256-CBC | getkeys `key` hex[:32] bytes | getkeys `key` hex[32:48] bytes |
