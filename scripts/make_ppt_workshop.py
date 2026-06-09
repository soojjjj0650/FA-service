"""
Knox 챗봇 개발 워크샵 PPT 생성기
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── 색상 ──────────────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0f, 0x17, 0x2a)
BLUE   = RGBColor(0x1e, 0x3a, 0x6e)
MBLUE  = RGBColor(0x2d, 0x5a, 0x9e)
LBLUE  = RGBColor(0x60, 0xa5, 0xfa)
ACCENT = RGBColor(0x38, 0xbd, 0xf8)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
GRAY   = RGBColor(0xf1, 0xf5, 0xf9)
DGRAY  = RGBColor(0x64, 0x74, 0x8b)
BLACK  = RGBColor(0x0f, 0x17, 0x2a)
GREEN  = RGBColor(0x10, 0xb9, 0x81)
ORANGE = RGBColor(0xf5, 0x9e, 0x0b)
RED    = RGBColor(0xef, 0x44, 0x44)
CODE_BG = RGBColor(0x1e, 0x29, 0x3b)
CODE_FG = RGBColor(0x93, 0xc5, 0xfd)
STR_FG  = RGBColor(0x86, 0xef, 0xac)
KEY_FG  = RGBColor(0xfb, 0xcf, 0x89)

W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H
BLANK = prs.slide_layouts[6]


def rect(sl, x, y, w, h, fill=None, line_color=None, line_pt=1):
    s = sl.shapes.add_shape(1, x, y, w, h)
    s.line.fill.background()
    if fill:
        s.fill.solid(); s.fill.fore_color.rgb = fill
    else:
        s.fill.background()
    if line_color:
        s.line.color.rgb = line_color; s.line.width = Pt(line_pt)
    else:
        s.line.fill.background()
    return s


def txt(sl, text, x, y, w, h, size=18, bold=False, color=BLACK,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    t = sl.shapes.add_textbox(x, y, w, h)
    tf = t.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.color.rgb = color; r.font.italic = italic
    return t


def code_block(sl, lines, x, y, w, h):
    """코드 블록 (다크 배경 + 컬러 텍스트)"""
    rect(sl, x, y, w, h, fill=CODE_BG)
    rect(sl, x, y, Inches(0.06), h, fill=ACCENT)
    tb = sl.shapes.add_textbox(x + Inches(0.15), y + Inches(0.12),
                                w - Inches(0.25), h - Inches(0.2))
    tf = tb.text_frame; tf.word_wrap = False
    first = True
    for line, color in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(0); p.space_after = Pt(0)
        r = p.add_run(); r.text = line
        r.font.size = Pt(11.5)
        r.font.color.rgb = color
        try:
            r.font.name = "Consolas"
        except Exception:
            pass
    return tb


def header(sl, step_label, title, subtitle=None, dark=False):
    bg = NAVY if dark else GRAY
    rect(sl, 0, 0, W, H, fill=bg)
    rect(sl, 0, 0, W, Inches(0.1), fill=ACCENT)
    step_color = ACCENT if dark else MBLUE
    title_color = WHITE if dark else NAVY
    sub_color = LBLUE if dark else DGRAY

    if step_label:
        txt(sl, step_label, Inches(0.5), Inches(0.18), Inches(2), Inches(0.55),
            size=12, bold=True, color=step_color)
    txt(sl, title, Inches(0.5), Inches(0.55) if step_label else Inches(0.22),
        Inches(12), Inches(0.75), size=26, bold=True, color=title_color)
    if subtitle:
        txt(sl, subtitle, Inches(0.5), Inches(1.18), Inches(12), Inches(0.45),
            size=14, color=sub_color, italic=True)
    rect(sl, Inches(0.4), Inches(1.5), W - Inches(0.8), Pt(1.5),
         fill=ACCENT if dark else LBLUE)


def chip(sl, text, x, y, color=MBLUE):
    w = Inches(len(text) * 0.14 + 0.4)
    rect(sl, x, y, w, Inches(0.36), fill=color)
    txt(sl, text, x, y + Inches(0.04), w, Inches(0.3),
        size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    return w


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — 표지
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
rect(sl, 0, 0, W, H, fill=NAVY)
rect(sl, 0, 0, Inches(0.3), H, fill=ACCENT)
rect(sl, Inches(9), Inches(1), Inches(5), Inches(6), fill=BLUE)
rect(sl, Inches(10), Inches(2), Inches(4), Inches(4.5), fill=RGBColor(0x1a, 0x32, 0x6b))

txt(sl, "🤖", Inches(0.7), Inches(1.4), Inches(2), Inches(1.4), size=60, color=WHITE)
txt(sl, "Knox Messenger\n챗봇 개발 가이드",
    Inches(0.7), Inches(2.5), Inches(8.5), Inches(2.2),
    size=40, bold=True, color=WHITE)
txt(sl, "봇 등록  ·  방화벽  ·  수신 URL  ·  메시지 API  ·  Adaptive Card",
    Inches(0.7), Inches(4.8), Inches(8.5), Inches(0.6),
    size=15, color=LBLUE, italic=True)
txt(sl, "Step-by-Step Workshop",
    Inches(0.7), Inches(6.4), Inches(5), Inches(0.5),
    size=13, color=RGBColor(0x94, 0xa3, 0xb8))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — 전체 흐름 개요
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, None, "전체 구성 한눈에 보기",
       "이 순서대로 실습합니다")

steps = [
    ("01", "봇 등록",      "Knox Portal에서\n챗봇 생성 & Token 발급"),
    ("02", "서버 준비",    "Python 서버 구성\n(FastAPI/Flask)"),
    ("03", "방화벽",       "서버 포트 80\n외부 수신 허용"),
    ("04", "수신 URL\n등록", "Knox에 Webhook\nURL 등록"),
    ("05", "수신 API",     "메시지 받는\nPOST 엔드포인트"),
    ("06", "발신 API",     "텍스트 메시지\n보내기"),
    ("07", "Media",        "파일·PDF\n전송"),
    ("08", "Adaptive\nCard", "버튼·입력창\nUI 카드"),
]

bw = Inches(1.5)
bh = Inches(3.8)
gap = Inches(0.12)
total = len(steps) * bw + (len(steps)-1) * gap
sx = (W - total) / 2
by = Inches(1.7)

for i, (num, title, desc) in enumerate(steps):
    bx = sx + i * (bw + gap)
    c = NAVY if i % 2 == 0 else BLUE
    rect(sl, bx, by, bw, bh, fill=c)
    rect(sl, bx, by, bw, Inches(0.08), fill=ACCENT)
    txt(sl, num, bx, by + Inches(0.12), bw, Inches(0.45),
        size=20, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    txt(sl, title, bx, by + Inches(0.6), bw, Inches(0.9),
        size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, desc, bx, by + Inches(1.55), bw, Inches(2.0),
        size=11, color=LBLUE, align=PP_ALIGN.CENTER)

    if i < len(steps)-1:
        txt(sl, "›", bx + bw, by + Inches(1.5), gap + Inches(0.05), Inches(0.6),
            size=18, color=ACCENT, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — STEP 01: 봇 등록
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 01", "Knox Portal — 챗봇 등록",
       "Knox Messenger 개발자 포털에서 봇을 생성하고 인증 정보를 발급받습니다")

# 좌측: 절차
lx = Inches(0.5)
items = [
    ("1", "Knox Messenger Portal 접속",
          "https://openapi.samsung.net  (운영)\nhttps://openapi.stage.samsung.net  (스테이지)"),
    ("2", "챗봇 애플리케이션 등록",
          "봇 이름, 설명, 프로필 이미지 설정"),
    ("3", "Access Token 발급",
          "API 호출 시 Authorization 헤더에 사용"),
    ("4", "System ID 확인",
          "메시지 서명/인증에 사용되는 식별자"),
]
for i, (num, title, desc) in enumerate(items):
    by = Inches(1.7) + i * Inches(1.2)
    rect(sl, lx, by, Inches(0.42), Inches(0.42),
         fill=ACCENT if i == 0 else MBLUE)
    txt(sl, num, lx, by + Inches(0.02), Inches(0.42), Inches(0.4),
        size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, title, lx + Inches(0.55), by, Inches(5.8), Inches(0.45),
        size=15, bold=True, color=NAVY)
    txt(sl, desc, lx + Inches(0.55), by + Inches(0.42), Inches(5.8), Inches(0.65),
        size=12, color=DGRAY)

# 우측: 발급되는 정보
rx = Inches(7.2)
rect(sl, rx, Inches(1.65), Inches(5.8), Inches(5.4), fill=CODE_BG)
rect(sl, rx, Inches(1.65), Inches(5.8), Inches(0.4), fill=BLUE)
txt(sl, "  발급되는 인증 정보", rx, Inches(1.65), Inches(5.8), Inches(0.4),
    size=13, bold=True, color=WHITE)

info_lines = [
    ("# .env 또는 환경변수에 저장", DGRAY),
    ("", WHITE),
    ("KNOX_MESSENGER_BASE_URL=https://openapi.samsung.net", CODE_FG),
    ("KNOX_ACCESS_TOKEN=b0df5ab5-****-****-****-****", STR_FG),
    ("KNOX_SYSTEM_ID=KCC10REST04505", STR_FG),
    ("KNOX_DEVICE_ID=211055033", STR_FG),
    ("", WHITE),
    ("# 스테이지 환경", DGRAY),
    ("KNOX_MESSENGER_BASE_URL=https://openapi.stage.samsung.net", CODE_FG),
    ("KNOX_ACCESS_TOKEN=c5e2b6bd-****-****-****-****", STR_FG),
    ("KNOX_DEVICE_ID=21005797091", STR_FG),
]
code_block(sl, info_lines, rx, Inches(2.1), Inches(5.8), Inches(4.7))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — 핵심 개념: 왜 방화벽(Port 80)을 열어야 하는가?
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "핵심 개념", "왜 방화벽(Port 80)을 열어야 할까?",
       "Knox 서버는 삼성 클라우드(외부)에 있습니다 — 메시지를 받으려면 내 서버 포트를 허용해야 합니다")

_arch_nodes = [
    ("👤",  "사용자",      "Knox 앱\n메시지 입력",              MBLUE, False),
    ("📡",  "Knox Server", "Samsung Cloud\nopenapi.samsung.net", BLUE,  False),
    ("🔥",  "방화벽",      "Port 80\n반드시 허용!",              RED,   True),
    ("🖥️", "내 서버",     "Server PC\n:80/message",            NAVY,  False),
]
_nbw  = Inches(2.3)
_nbh  = Inches(2.4)
_ngap = Inches(0.78)
_ntot = len(_arch_nodes) * _nbw + (len(_arch_nodes) - 1) * _ngap
_nsx  = (W - _ntot) / 2
_nby  = Inches(1.72)

for _ni, (_nico, _ntit, _ndsc, _nc, _nfw) in enumerate(_arch_nodes):
    _nbx = _nsx + _ni * (_nbw + _ngap)
    if _nfw:
        rect(sl, _nbx - Inches(0.05), _nby - Inches(0.05),
             _nbw + Inches(0.1), _nbh + Inches(0.1),
             fill=None, line_color=RED, line_pt=3)
    rect(sl, _nbx, _nby, _nbw, _nbh, fill=_nc)
    rect(sl, _nbx, _nby, _nbw, Inches(0.1),
         fill=RED if _nfw else ACCENT)
    txt(sl, _nico, _nbx, _nby + Inches(0.1),  _nbw, Inches(0.8),
        size=28, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, _ntit, _nbx, _nby + Inches(0.88), _nbw, Inches(0.5),
        size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, _ndsc, _nbx, _nby + Inches(1.45), _nbw, Inches(0.8),
        size=10.5, color=WHITE if _nfw else LBLUE,
        align=PP_ALIGN.CENTER)
    if _ni < len(_arch_nodes) - 1:
        _nax = _nbx + _nbw
        _nac = RED if _ni == 1 else ACCENT
        txt(sl, "▶", _nax, _nby + Inches(0.82), _ngap, Inches(0.6),
            size=22, color=_nac, align=PP_ALIGN.CENTER)

_nfwbx  = _nsx + 2 * (_nbw + _ngap)
_nfwmid = _nfwbx + _nbw / 2
_nbot   = _nby + _nbh

# external zone label
rect(sl, _nsx - Inches(0.1), _nbot + Inches(0.1),
     _nfwmid - _nsx + Inches(0.1), Inches(0.38),
     fill=RGBColor(0x05, 0x27, 0x14))
txt(sl, "🌐  외부 네트워크 (Samsung Cloud / 인터넷)",
    _nsx, _nbot + Inches(0.13),
    _nfwmid - _nsx, Inches(0.32),
    size=11, bold=True, color=GREEN)

# internal zone label
rect(sl, _nfwmid, _nbot + Inches(0.1),
     W - _nfwmid - _nsx + Inches(0.1), Inches(0.38),
     fill=RGBColor(0x0c, 0x16, 0x32))
txt(sl, "🏢  사내 네트워크",
    _nfwmid + Inches(0.1), _nbot + Inches(0.13),
    W - _nfwmid - _nsx, Inches(0.32),
    size=11, bold=True, color=LBLUE)

# key message box
_nmy = _nbot + Inches(0.65)
rect(sl, Inches(0.4), _nmy, W - Inches(0.8), Inches(1.5), fill=CODE_BG)
rect(sl, Inches(0.4), _nmy, Inches(0.06), Inches(1.5), fill=RED)
txt(sl, "Knox 서버(외부)  →  방화벽  →  내 서버(내부)  포트 80 인바운드 요청",
    Inches(0.65), _nmy + Inches(0.1), W - Inches(1.2), Inches(0.5),
    size=15, bold=True, color=WHITE)
txt(sl, "방화벽에서 TCP 포트 80 인바운드를 허용해야 Knox 메시지를 수신할 수 있습니다",
    Inches(0.65), _nmy + Inches(0.6), W - Inches(1.2), Inches(0.42),
    size=13, color=LBLUE)
txt(sl, "💡  내 서버 IP를 Knox Portal에 Receive URL로 등록합니다  (STEP 04에서 실습)",
    Inches(0.65), _nmy + Inches(1.08), W - Inches(1.2), Inches(0.36),
    size=12, color=ORANGE)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — STEP 02+03: 서버 & 방화벽
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 02 + 03", "서버 구성 & 방화벽 설정",
       "Knox가 메시지를 보낼 수 있도록 서버 포트를 열어줍니다")

# 좌: 서버 구성
lx = Inches(0.4)
rect(sl, lx, Inches(1.65), Inches(6.1), Inches(0.45), fill=BLUE)
txt(sl, "  🖥️  서버 구성 (FastAPI 예시)",
    lx, Inches(1.65), Inches(6.1), Inches(0.45),
    size=13, bold=True, color=WHITE)

server_lines = [
    ("# pip install fastapi uvicorn", DGRAY),
    ("from fastapi import FastAPI, Request", CODE_FG),
    ("", WHITE),
    ("app = FastAPI()", CODE_FG),
    ("", WHITE),
    ("@app.post(\"/message\")", KEY_FG),
    ("async def receive(request: Request):", CODE_FG),
    ("    data = await request.json()", CODE_FG),
    ("    print(data)  # 수신 확인", DGRAY),
    ("    return {\"status\": \"ok\"}", STR_FG),
    ("", WHITE),
    ("# 실행: uvicorn main:app --port 80", DGRAY),
]
code_block(sl, server_lines, lx, Inches(2.15), Inches(6.1), Inches(4.9))

# 우: 방화벽
rx = Inches(6.9)
rect(sl, rx, Inches(1.65), Inches(6.1), Inches(0.45), fill=RED)
txt(sl, "  🔥  방화벽 설정 (Windows)",
    rx, Inches(1.65), Inches(6.1), Inches(0.45),
    size=13, bold=True, color=WHITE)

fw_lines = [
    ("# 관리자 PowerShell에서 실행", DGRAY),
    ("", WHITE),
    ("netsh advfirewall firewall add rule \\", CODE_FG),
    ("  name=\"Knox-Chatbot\" \\", STR_FG),
    ("  protocol=TCP dir=in \\", STR_FG),
    ("  localport=80 action=allow", STR_FG),
    ("", WHITE),
    ("# 확인", DGRAY),
    ("netsh advfirewall firewall show rule \\", CODE_FG),
    ("  name=\"Knox-Chatbot\"", STR_FG),
    ("", WHITE),
    ("# 포트 리스닝 확인", DGRAY),
    ("netstat -an | findstr :80", CODE_FG),
]
code_block(sl, fw_lines, rx, Inches(2.15), Inches(6.1), Inches(4.9))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — STEP 04: 수신 URL 등록
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 04", "수신 URL (Webhook) 등록",
       "Knox Portal에 서버 주소를 등록하면 메시지가 해당 URL로 전달됩니다")

# 흐름 다이어그램
flow_items = [
    ("👤", "사용자", "Knox 앱에서\n메시지 입력"),
    ("📡", "Knox\nServer", "메시지를\n봇에 전달"),
    ("🖥️", "내 서버", "POST /message\n수신 처리"),
]
bw = Inches(3.2)
bh = Inches(2.0)
gap = Inches(0.8)
sx = Inches(0.8)
by = Inches(1.7)
for i, (icon, title, desc) in enumerate(flow_items):
    bx = sx + i * (bw + gap)
    c = NAVY if i == 2 else BLUE
    rect(sl, bx, by, bw, bh, fill=c)
    rect(sl, bx, by, bw, Inches(0.07), fill=ACCENT)
    txt(sl, icon, bx, by + Inches(0.1), bw, Inches(0.7),
        size=28, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, title, bx, by + Inches(0.8), bw, Inches(0.5),
        size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, desc, bx, by + Inches(1.3), bw, Inches(0.65),
        size=12, color=LBLUE, align=PP_ALIGN.CENTER)
    if i < len(flow_items)-1:
        txt(sl, "▶", bx + bw, by + Inches(0.65), gap, Inches(0.6),
            size=22, color=ACCENT, align=PP_ALIGN.CENTER)

# 등록 API
rect(sl, Inches(0.4), Inches(3.9), Inches(12.5), Inches(0.4), fill=BLUE)
txt(sl, "  Knox Portal API — 수신 URL 등록",
    Inches(0.4), Inches(3.9), Inches(12.5), Inches(0.4),
    size=13, bold=True, color=WHITE)

reg_lines = [
    ("PUT  https://openapi.samsung.net/messenger/bot/api/v2.0/bot/chatbot/receive-url", CODE_FG),
    ("", WHITE),
    ("Authorization: Bearer {ACCESS_TOKEN}", KEY_FG),
    ("System-ID: {SYSTEM_ID}", KEY_FG),
    ("Content-Type: application/json", KEY_FG),
    ("", WHITE),
    ("{", WHITE),
    ("  \"receiveUrl\": \"http://10.246.9.74:80/message\",", STR_FG),
    ("  \"deviceId\":   211055033", STR_FG),
    ("}", WHITE),
]
code_block(sl, reg_lines, Inches(0.4), Inches(4.35), Inches(12.5), Inches(2.8))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — STEP 05: 메시지 수신 API
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 05", "메시지 수신 API",
       "Knox가 내 서버로 보내주는 메시지의 형태를 알아봅니다")

# 좌: 수신 페이로드
lx = Inches(0.4)
rect(sl, lx, Inches(1.65), Inches(6.1), Inches(0.4), fill=MBLUE)
txt(sl, "  📥  수신 페이로드 (POST /message)",
    lx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

recv_lines = [
    ("{", WHITE),
    ("  \"msgType\":    \"TEXT\",", CODE_FG),
    ("  \"chatMsg\":    \"SN-12345\",", STR_FG),  # 텍스트 메시지
    ("  \"chatroomId\": 987654321,", CODE_FG),
    ("  \"sender\":     \"921475588965797889\",", CODE_FG),
    ("  \"msgId\":      1718000000000", CODE_FG),
    ("}", WHITE),
    ("", WHITE),
    ("# Adaptive Card 수신 시", DGRAY),
    ("{", WHITE),
    ("  \"msgType\":  \"ADAPTIVE_CARD\",", KEY_FG),
    ("  \"chatMsg\":  \"{\\\"sn\\\":\\\"SN-12345\\\"}\",", STR_FG),
    ("  \"chatroomId\": 987654321", CODE_FG),
    ("}", WHITE),
]
code_block(sl, recv_lines, lx, Inches(2.1), Inches(6.1), Inches(5.0))

# 우: 처리 코드
rx = Inches(6.9)
rect(sl, rx, Inches(1.65), Inches(6.1), Inches(0.4), fill=MBLUE)
txt(sl, "  ⚙️  처리 예시",
    rx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

handle_lines = [
    ("@app.post(\"/message\")", KEY_FG),
    ("async def receive(request: Request):", CODE_FG),
    ("    data = await request.json()", CODE_FG),
    ("", WHITE),
    ("    msg_type    = data.get(\"msgType\")", CODE_FG),
    ("    chat_msg    = data.get(\"chatMsg\", \"\")", CODE_FG),
    ("    chatroom_id = data.get(\"chatroomId\")", CODE_FG),
    ("", WHITE),
    ("    if msg_type == \"ADAPTIVE_CARD\":", KEY_FG),
    ("        card = json.loads(chat_msg)", CODE_FG),
    ("        sn   = card.get(\"sn\", \"\")", CODE_FG),
    ("    else:", KEY_FG),
    ("        sn = chat_msg.strip()", CODE_FG),
    ("", WHITE),
    ("    # SN으로 분석 파이프라인 실행", DGRAY),
    ("    await run_analysis(sn, chatroom_id)", CODE_FG),
    ("    return {\"status\": \"ok\"}", STR_FG),
]
code_block(sl, handle_lines, rx, Inches(2.1), Inches(6.1), Inches(5.0))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — STEP 06: 텍스트 메시지 발신
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 06", "텍스트 메시지 발신",
       "분석 결과나 안내 메시지를 사용자에게 보냅니다")

# 좌: API 스펙
lx = Inches(0.4)
rect(sl, lx, Inches(1.65), Inches(6.1), Inches(0.4), fill=GREEN)
txt(sl, "  📤  발신 API",
    lx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

send_lines = [
    ("POST  /messenger/message/api/v2.0/message/chatRequest", CODE_FG),
    ("", WHITE),
    ("Authorization: Bearer {ACCESS_TOKEN}", KEY_FG),
    ("System-ID: {SYSTEM_ID}", KEY_FG),
    ("", WHITE),
    ("{", WHITE),
    ("  \"requestId\":  1718000000000,", CODE_FG),
    ("  \"chatroomId\": 987654321,", CODE_FG),
    ("  \"chatMessageParams\": [{", CODE_FG),
    ("    \"msgId\":   1718000000000,", CODE_FG),
    ("    \"msgType\": 0,", KEY_FG),   # 텍스트
    ("    \"chatMsg\": \"분석이 완료되었습니다.\",", STR_FG),
    ("    \"msgTtl\":  7200", CODE_FG),
    ("  }]", CODE_FG),
    ("}", WHITE),
]
code_block(sl, send_lines, lx, Inches(2.1), Inches(6.1), Inches(5.0))

# 우: 주요 msgType
rx = Inches(6.9)
rect(sl, rx, Inches(1.65), Inches(6.1), Inches(0.4), fill=GREEN)
txt(sl, "  📋  msgType 종류",
    rx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

type_items = [
    ("0", "TEXT",          "일반 텍스트 메시지"),
    ("1", "MEDIA",         "파일 첨부 (PDF, ZIP 등)"),
    ("─", "ADAPTIVE_CARD", "버튼·입력 UI 카드"),
]
for i, (num, name, desc) in enumerate(type_items):
    by2 = Inches(2.2) + i * Inches(1.3)
    c = ACCENT if i == 0 else (ORANGE if i == 1 else MBLUE)
    rect(sl, rx + Inches(0.15), by2, Inches(0.55), Inches(0.55), fill=c)
    txt(sl, num, rx + Inches(0.15), by2 + Inches(0.04),
        Inches(0.55), Inches(0.45), size=18, bold=True,
        color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, name, rx + Inches(0.85), by2, Inches(3.5), Inches(0.45),
        size=15, bold=True, color=NAVY)
    txt(sl, desc, rx + Inches(0.85), by2 + Inches(0.45), Inches(5.0), Inches(0.5),
        size=13, color=DGRAY)

rect(sl, rx, Inches(6.1), Inches(6.1), Inches(0.95), fill=CODE_BG)
txt(sl, "💡  chatroomId는 수신 메시지의 chatroomId를 그대로 사용합니다",
    rx + Inches(0.2), Inches(6.15), Inches(5.8), Inches(0.8),
    size=12, color=LBLUE)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — STEP 07: Media 메시지 (파일 전송)
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 07", "Media 메시지 — 파일 전송",
       "PDF, ZIP 등 파일을 Knox 파일서버에 업로드 후 메시지로 전송합니다")

# 2단계 흐름
step_items = [
    ("① 파일 업로드", ORANGE),
    ("② 파일 메시지 전송", GREEN),
]
bw2 = Inches(6.1)
for i, (label, c) in enumerate(step_items):
    bx2 = Inches(0.4) + i * Inches(6.6)
    rect(sl, bx2, Inches(1.65), bw2, Inches(0.4), fill=c)
    txt(sl, f"  {label}", bx2, Inches(1.65), bw2, Inches(0.4),
        size=13, bold=True, color=WHITE)

upload_lines = [
    ("PUT  /messenger/file/api/v2.0/file/v1s/file/{filename}", CODE_FG),
    ("", WHITE),
    ("Content-Type: binary/octet-stream", KEY_FG),
    ("filename:       r20240610120000.pdf", KEY_FG),
    ("x-device-id:    {AES256(device_id)}", KEY_FG),
    ("x-request-time: {AES256(server_time)}", KEY_FG),
    ("", WHITE),
    ("# Body: 파일 바이너리", DGRAY),
    ("", WHITE),
    ("# 응답", DGRAY),
    ("{\"download_url\": \"https://.../{filename}\"}", STR_FG),
]
code_block(sl, upload_lines, Inches(0.4), Inches(2.1), Inches(6.1), Inches(4.9))

media_lines = [
    ("POST  /messenger/message/api/v2.0/message/chatRequest", CODE_FG),
    ("", WHITE),
    ("{", WHITE),
    ("  \"chatroomId\": 987654321,", CODE_FG),
    ("  \"chatMessageParams\": [{", CODE_FG),
    ("    \"msgType\": 1,", KEY_FG),  # MEDIA
    ("    \"chatMsg\": JSON.stringify({", CODE_FG),
    ("      \"media\": {", CODE_FG),
    ("        \"extension\": \"pdf\",", STR_FG),
    ("        \"type\":      \"file\",", STR_FG),
    ("        \"filename\":  \"SN12345_analysis.pdf\",", STR_FG),
    ("        \"url\":       \"{download_url}\"", STR_FG),
    ("      }", CODE_FG),
    ("    })", CODE_FG),
    ("  }]", CODE_FG),
    ("}", WHITE),
]
code_block(sl, media_lines, Inches(7.0), Inches(2.1), Inches(6.1), Inches(4.9))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — STEP 08: Adaptive Card
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 08", "Adaptive Card — 인터랙티브 UI",
       "버튼, 입력창이 있는 카드 형태의 메시지를 보낼 수 있습니다")

# 좌: 카드 JSON
lx = Inches(0.4)
rect(sl, lx, Inches(1.65), Inches(6.1), Inches(0.4), fill=MBLUE)
txt(sl, "  🃏  Adaptive Card JSON 구조",
    lx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

card_lines = [
    ("{", WHITE),
    ("  \"type\": \"AdaptiveCard\",", CODE_FG),
    ("  \"body\": [", CODE_FG),
    ("    {\"type\":\"TextBlock\",", STR_FG),
    ("     \"text\":\"SN을 입력하세요\",", STR_FG),
    ("     \"size\":\"Large\", \"weight\":\"Bolder\"},", STR_FG),
    ("    {\"type\":\"Input.Text\",", KEY_FG),
    ("     \"id\":\"sn\",", KEY_FG),
    ("     \"placeholder\":\"예) SM-S928N/KOO\"}", KEY_FG),
    ("  ],", CODE_FG),
    ("  \"actions\": [{", CODE_FG),
    ("    \"type\":  \"Action.Submit\",", STR_FG),
    ("    \"title\": \"분석 시작\"", STR_FG),
    ("  }]", CODE_FG),
    ("}", WHITE),
]
code_block(sl, card_lines, lx, Inches(2.1), Inches(6.1), Inches(5.0))

# 우: 전송 API + 수신 처리
rx = Inches(6.9)
rect(sl, rx, Inches(1.65), Inches(6.1), Inches(0.4), fill=MBLUE)
txt(sl, "  📤  카드 전송 & 수신 처리",
    rx, Inches(1.65), Inches(6.1), Inches(0.4),
    size=13, bold=True, color=WHITE)

send_card_lines = [
    ("# 발신 — msgType: ADAPTIVE_CARD", DGRAY),
    ("{", WHITE),
    ("  \"msgType\": \"ADAPTIVE_CARD\",", KEY_FG),
    ("  \"chatMsg\": \"{카드 JSON 문자열}\"", STR_FG),
    ("}", WHITE),
    ("", WHITE),
    ("# 수신 — 사용자가 Submit하면", DGRAY),
    ("{", WHITE),
    ("  \"msgType\": \"ADAPTIVE_CARD\",", KEY_FG),
    ("  \"chatMsg\": \"{\\\"sn\\\":\\\"SM-S928N/KOO\\\"}\"", STR_FG),
    ("}", WHITE),
    ("", WHITE),
    ("# 파싱", DGRAY),
    ("data  = json.loads(chat_msg)", CODE_FG),
    ("sn    = data.get(\"sn\", \"\")", CODE_FG),
    ("", WHITE),
    ("# → SN으로 분석 실행!", DGRAY),
]
code_block(sl, send_card_lines, rx, Inches(2.1), Inches(6.1), Inches(5.0))


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 11 — 실습 체크리스트
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
rect(sl, 0, 0, W, H, fill=NAVY)
rect(sl, 0, 0, W, Inches(0.1), fill=ACCENT)
rect(sl, 0, 0, Inches(0.3), H, fill=ACCENT)

txt(sl, "실습 체크리스트", Inches(0.6), Inches(0.2), Inches(11), Inches(0.7),
    size=28, bold=True, color=WHITE)
rect(sl, Inches(0.4), Inches(0.9), W - Inches(0.8), Pt(1), fill=BLUE)

checks = [
    ("01", "Knox Portal 접속 → 챗봇 등록 → Access Token 확인"),
    ("02", "Python 서버 생성 → POST /message 엔드포인트 구현"),
    ("03", "방화벽 포트 80 오픈 → 외부에서 접속 테스트"),
    ("04", "Knox Portal에 수신 URL 등록"),
    ("05", "Knox 앱에서 봇 찾아서 메시지 전송 → 서버 로그 확인"),
    ("06", "텍스트 답장 발신 API 호출 → 챗봇 응답 확인"),
    ("07", "PDF 파일 업로드 → Media 메시지 전송"),
    ("08", "Adaptive Card 전송 → SN 입력 → 수신 처리"),
]

cols = 2
for i, (num, desc) in enumerate(checks):
    col = i % cols
    row = i // cols
    bx = Inches(0.5) + col * Inches(6.6)
    by = Inches(1.1) + row * Inches(1.38)

    rect(sl, bx, by, Inches(6.3), Inches(1.15), fill=BLUE)
    rect(sl, bx, by, Inches(0.1), Inches(1.15), fill=ACCENT)
    rect(sl, bx + Inches(0.2), by + Inches(0.32),
         Inches(0.42), Inches(0.42), fill=MBLUE)
    txt(sl, "☐", bx + Inches(0.2), by + Inches(0.3),
        Inches(0.45), Inches(0.45), size=16, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, num, bx + Inches(0.75), by + Inches(0.1),
        Inches(0.7), Inches(0.4), size=12, bold=True, color=ACCENT)
    txt(sl, desc, bx + Inches(0.75), by + Inches(0.5),
        Inches(5.3), Inches(0.6), size=13, color=WHITE)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — 마무리
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
rect(sl, 0, 0, W, H, fill=NAVY)
rect(sl, 0, 0, Inches(0.3), H, fill=ACCENT)
rect(sl, Inches(9.5), Inches(1.5), Inches(4.5), Inches(5.5), fill=BLUE)
rect(sl, Inches(10.5), Inches(2.5), Inches(3.5), Inches(4), fill=RGBColor(0x1a, 0x32, 0x6b))

txt(sl, "🎉", Inches(0.7), Inches(1.5), Inches(2), Inches(1.4), size=60, color=WHITE)
txt(sl, "Knox 챗봇 완성!",
    Inches(0.7), Inches(2.7), Inches(9), Inches(1.2),
    size=42, bold=True, color=WHITE)
txt(sl, "봇 등록  →  방화벽  →  수신 URL  →  발신 API  →  Adaptive Card",
    Inches(0.7), Inches(3.9), Inches(9), Inches(0.6),
    size=15, color=LBLUE)

summaries = [
    "메시지 수신: POST /message (msgType, chatMsg, chatroomId)",
    "메시지 발신: POST /chatRequest (msgType 0=텍스트, 1=파일)",
    "Adaptive Card: msgType=ADAPTIVE_CARD, chatMsg=JSON 문자열",
]
for i, s in enumerate(summaries):
    txt(sl, f"✓  {s}", Inches(0.7), Inches(4.7) + i * Inches(0.5),
        Inches(9), Inches(0.45), size=13, color=WHITE)

txt(sl, "Q & A", Inches(0.7), Inches(6.5), Inches(4), Inches(0.6),
    size=20, bold=True, color=ACCENT)


# ── 저장 ──────────────────────────────────────────────────────────────────────
out = "/home/user/FA-service/knox_chatbot_개발가이드.pptx"
prs.save(out)
print(f"저장 완료: {out}")
