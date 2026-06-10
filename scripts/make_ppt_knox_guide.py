"""
Knox Teams 메신저 만들기 - PPT 가이드 생성
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import os

# ── 색상 ──────────────────────────────────────────────────────────────────────
NAVY    = RGBColor(0x0f, 0x17, 0x2a)
BLUE    = RGBColor(0x1e, 0x3a, 0x6e)
MBLUE   = RGBColor(0x2d, 0x5a, 0x9e)
LBLUE   = RGBColor(0x60, 0xa5, 0xfa)
ACCENT  = RGBColor(0x38, 0xbd, 0xf8)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
GRAY    = RGBColor(0xf1, 0xf5, 0xf9)
DGRAY   = RGBColor(0x64, 0x74, 0x8b)
GREEN   = RGBColor(0x10, 0xb9, 0x81)
ORANGE  = RGBColor(0xf5, 0x9e, 0x0b)
RED     = RGBColor(0xef, 0x44, 0x44)
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


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
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


def txt(sl, text, x, y, w, h, size=18, bold=False, color=WHITE,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    t = sl.shapes.add_textbox(x, y, w, h)
    tf = t.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.color.rgb = color; r.font.italic = italic
    return t


def header(sl, step_label, title, subtitle=None):
    rect(sl, 0, 0, W, H, fill=NAVY)
    rect(sl, 0, 0, W, Inches(0.1), fill=ACCENT)
    if step_label:
        txt(sl, step_label, Inches(0.5), Inches(0.18), Inches(3), Inches(0.5),
            size=12, bold=True, color=ACCENT)
    txt(sl, title, Inches(0.5), Inches(0.55) if step_label else Inches(0.25),
        Inches(12), Inches(0.75), size=26, bold=True, color=WHITE)
    if subtitle:
        txt(sl, subtitle, Inches(0.5), Inches(1.18), Inches(12), Inches(0.45),
            size=13, color=LBLUE, italic=True)
    rect(sl, Inches(0.4), Inches(1.5), W - Inches(0.8), Pt(1.5), fill=ACCENT)


def photo_box(sl, x, y, w, h, label="캡쳐 필요"):
    rect(sl, x, y, w, h, fill=RGBColor(0x12, 0x22, 0x3a), line_color=LBLUE, line_pt=1.5)
    txt(sl, f"📷   {label}", x, y + h/2 - Inches(0.35), w, Inches(0.7),
        size=15, bold=True, color=LBLUE, align=PP_ALIGN.CENTER)


def path_box(sl, x, y, w, path_text):
    rect(sl, x, y, w, Inches(0.5), fill=BLUE)
    rect(sl, x, y, Inches(0.06), Inches(0.5), fill=ACCENT)
    txt(sl, path_text, x + Inches(0.15), y + Inches(0.06), w - Inches(0.2), Inches(0.4),
        size=12, bold=True, color=WHITE)


def info_row(sl, x, y, w, label, value, label_color=ACCENT):
    txt(sl, label, x, y, Inches(2.5), Inches(0.38),
        size=12, bold=True, color=label_color)
    txt(sl, value, x + Inches(2.6), y, w - Inches(2.6), Inches(0.38),
        size=12, color=WHITE)


def note_box(sl, x, y, w, text, color=ORANGE):
    rect(sl, x, y, w, Inches(0.5), fill=CODE_BG)
    rect(sl, x, y, Inches(0.06), Inches(0.5), fill=color)
    txt(sl, text, x + Inches(0.15), y + Inches(0.06),
        w - Inches(0.2), Inches(0.4), size=11, color=WHITE)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — 표지
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
rect(sl, 0, 0, W, H, fill=NAVY)
rect(sl, 0, 0, Inches(0.3), H, fill=ACCENT)
rect(sl, Inches(9.2), Inches(1.0), Inches(4.8), Inches(6.0), fill=BLUE)
rect(sl, Inches(10.0), Inches(2.0), Inches(4.0), Inches(4.5), fill=RGBColor(0x1a, 0x32, 0x6b))

txt(sl, "💬", Inches(0.7), Inches(1.3), Inches(1.8), Inches(1.4), size=58, color=WHITE)
txt(sl, "Knox Teams\n메신저 만들기",
    Inches(0.7), Inches(2.5), Inches(8.2), Inches(2.3),
    size=42, bold=True, color=WHITE)
txt(sl, "봇 등록  ·  방화벽  ·  서버 등록  ·  API 연결",
    Inches(0.7), Inches(4.9), Inches(8.2), Inches(0.55),
    size=15, color=LBLUE, italic=True)
txt(sl, "Knox C&C Suite Developer Guide",
    Inches(0.7), Inches(6.1), Inches(6.5), Inches(0.5),
    size=13, color=DGRAY)
txt(sl, "http://developers.samsung.net/static/knoxcenter/main.html#",
    Inches(0.7), Inches(6.6), Inches(8.0), Inches(0.45),
    size=11, color=LBLUE, italic=True)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — 전체 흐름 개요
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, None, "전체 구성", "이 순서대로 진행합니다")

steps = [
    ("01", "챗봇 아이디\n생성",    "Knox Portal에서\n봇 계정 신청"),
    ("02", "방화벽\n연결",         "서버 포트 개방\n(IN/OUT)"),
    ("03", "Knox 서버\n등록",      "System ID &\nToken 발급"),
    ("04", "API 연결\n챗봇 방 생성", "Device 등록\n대화방 생성"),
    ("05", "FAQ",                  "문의처 &\nKnox Support"),
]

bw = Inches(2.3)
bh = Inches(3.8)
gap = Inches(0.17)
total = len(steps) * bw + (len(steps) - 1) * gap
sx = (W - total) / 2
by = Inches(1.7)

for i, (num, title, desc) in enumerate(steps):
    bx = sx + i * (bw + gap)
    c = NAVY if i % 2 == 0 else BLUE
    rect(sl, bx, by, bw, bh, fill=c)
    rect(sl, bx, by, bw, Inches(0.08), fill=ACCENT)
    txt(sl, num, bx, by + Inches(0.12), bw, Inches(0.5),
        size=22, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    txt(sl, title, bx, by + Inches(0.65), bw, Inches(1.1),
        size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, desc, bx, by + Inches(1.8), bw, Inches(1.8),
        size=11, color=LBLUE, align=PP_ALIGN.CENTER)
    if i < len(steps) - 1:
        txt(sl, "›", bx + bw, by + Inches(1.5), gap + Inches(0.08), Inches(0.6),
            size=18, color=ACCENT, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — STEP 01: 챗봇 아이디 생성하기
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 01", "챗봇 아이디 생성하기",
       "Knox Portal에서 봇 계정을 신청합니다. 결재 후 챗봇 아이디가 생성됩니다.")

# 경로 안내
path_box(sl, Inches(0.5), Inches(1.7),
         W - Inches(1.0),
         "Home  →  My Interface  →  Bot  →  봇관리  →  봇계정신청")

# 결재 정보
rect(sl, Inches(0.5), Inches(2.35), Inches(3.8), Inches(2.0), fill=BLUE)
rect(sl, Inches(0.5), Inches(2.35), Inches(3.8), Inches(0.08), fill=ACCENT)
txt(sl, "  결재 정보",
    Inches(0.5), Inches(2.38), Inches(3.8), Inches(0.42),
    size=13, bold=True, color=WHITE)
for i, item in enumerate(["파트장  결재", "경영지원  합의"]):
    txt(sl, f"•  {item}",
        Inches(0.7), Inches(2.9) + i * Inches(0.48), Inches(3.4), Inches(0.45),
        size=13, color=LBLUE)

# 캡쳐 박스
photo_box(sl, Inches(4.5), Inches(2.35), Inches(8.5), Inches(4.7),
          "봇계정신청 화면 캡쳐")

note_box(sl, Inches(0.5), Inches(4.5), Inches(3.8),
         "💡 결재 완료 후 아이디 생성 확인", color=GREEN)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — STEP 02: 방화벽 개념도
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 02", "방화벽 연결하기 — 개념도",
       "내 서버와 Knox 서버 간 발신(Outbound) / 수신(Inbound) 두 방향 모두 정책 등록이 필요합니다")

# 3개 컴포넌트 박스
nodes = [
    ("🖥️", "내 서버", "My Server\nPort 80", MBLUE),
    ("🔥", "방화벽",  "Firewall\n개방 필요", RED),
    ("📡", "Knox 서버", "openapi.samsung.net\n(Stage / Production)", BLUE),
]
nbw = Inches(3.0)
nbh = Inches(2.0)
ngap = Inches(1.6)
ntot = len(nodes) * nbw + (len(nodes) - 1) * ngap
nsx  = (W - ntot) / 2
nby  = Inches(1.72)

for i, (icon, title, sub, c) in enumerate(nodes):
    nbx = nsx + i * (nbw + ngap)
    rect(sl, nbx, nby, nbw, nbh, fill=c)
    rect(sl, nbx, nby, nbw, Inches(0.1), fill=ACCENT if c != RED else RED)
    txt(sl, icon,  nbx, nby + Inches(0.1),  nbw, Inches(0.7),
        size=28, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, title, nbx, nby + Inches(0.8),  nbw, Inches(0.45),
        size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, sub,   nbx, nby + Inches(1.28), nbw, Inches(0.65),
        size=10, color=LBLUE if c != RED else WHITE, align=PP_ALIGN.CENTER)

# 화살표 행 — Outbound (위)
aw_y = nby + Inches(0.3)
for i in range(len(nodes) - 1):
    ax = nsx + (i + 1) * nbw + i * ngap
    txt(sl, "─────▶",
        ax, aw_y, ngap, Inches(0.5),
        size=18, bold=True, color=GREEN, align=PP_ALIGN.CENTER)
txt(sl, "발신 (Outbound)  Port 80/443",
    nsx + nbw, aw_y - Inches(0.35), ntot - nbw * 2, Inches(0.38),
    size=11, bold=True, color=GREEN, align=PP_ALIGN.CENTER)

# 화살표 행 — Inbound (아래)
aw_y2 = nby + nbh - Inches(0.55)
for i in range(len(nodes) - 1):
    ax = nsx + (i + 1) * nbw + i * ngap
    txt(sl, "◀─────",
        ax, aw_y2, ngap, Inches(0.5),
        size=18, bold=True, color=RED, align=PP_ALIGN.CENTER)
txt(sl, "수신 (Inbound)  Port 80  ← 반드시 허용!",
    nsx + nbw, aw_y2 + Inches(0.4), ntot - nbw * 2, Inches(0.38),
    size=11, bold=True, color=RED, align=PP_ALIGN.CENTER)

# 핵심 메시지
msg_y = nby + nbh + Inches(0.9)
rect(sl, Inches(0.4), msg_y, W - Inches(0.8), Inches(1.5), fill=CODE_BG)
rect(sl, Inches(0.4), msg_y, Inches(0.06), Inches(1.5), fill=RED)
txt(sl, "Knox 서버(외부)  →  방화벽  →  내 서버 Port 80  으로 인바운드 HTTP 요청이 들어옵니다",
    Inches(0.65), msg_y + Inches(0.08), W - Inches(1.2), Inches(0.5),
    size=14, bold=True, color=WHITE)
txt(sl, "수신(Inbound) 정책:  Knox 서버 출발지 IP  →  내 서버 IP  Port 80  허용",
    Inches(0.65), msg_y + Inches(0.58), W - Inches(1.2), Inches(0.38),
    size=12, color=LBLUE)
txt(sl, "발신(Outbound) 정책:  내 서버 IP  →  openapi.samsung.net  Port 80, 443  허용",
    Inches(0.65), msg_y + Inches(0.98), W - Inches(1.2), Inches(0.38),
    size=12, color=GREEN)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — STEP 02: 방화벽 정책 상세 (Stage + Production)
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 02", "방화벽 정책 상세",
       "스테이지(개발)와 운영 서버의 IP/포트 정보를 방화벽 담당자에게 전달합니다")

def fw_panel(sl, ox, title, hdr_color, out_ip, out_host, in_ips):
    pw = Inches(6.0)
    # 제목
    rect(sl, ox, Inches(1.65), pw, Inches(0.42), fill=hdr_color)
    txt(sl, f"  {title}", ox, Inches(1.65), pw, Inches(0.42),
        size=13, bold=True, color=WHITE)

    # 발신
    rect(sl, ox, Inches(2.12), pw, Inches(0.36), fill=RGBColor(0x06, 0x3a, 0x20))
    txt(sl, "  발신 (Outbound) — 내 서버  →  Knox 서버",
        ox, Inches(2.12), pw, Inches(0.36), size=11, bold=True, color=GREEN)

    out_lines = [
        ("출발지", f"내 서버 IP   :   Port 80"),
        ("목적지", f"{out_ip}"),
        ("Host",   f"{out_host}"),
        ("포트",   "80,  443"),
    ]
    for j, (k, v) in enumerate(out_lines):
        by = Inches(2.52) + j * Inches(0.38)
        rect(sl, ox, by, Inches(1.3), Inches(0.38),
             fill=RGBColor(0x0c, 0x2a, 0x18))
        txt(sl, k, ox + Inches(0.1), by + Inches(0.04),
            Inches(1.2), Inches(0.32), size=11, bold=True, color=GREEN)
        txt(sl, v, ox + Inches(1.35), by + Inches(0.04),
            pw - Inches(1.4), Inches(0.32), size=11, color=WHITE)

    # 수신
    ib_y = Inches(4.05)
    rect(sl, ox, ib_y, pw, Inches(0.36), fill=RGBColor(0x4a, 0x0e, 0x0e))
    txt(sl, "  수신 (Inbound) — Knox 서버  →  내 서버  ⚠ 반드시 허용",
        ox, ib_y, pw, Inches(0.36), size=11, bold=True, color=RED)

    in_lines = [
        ("출발지", in_ips),
        ("목적지", "내 서버 IP"),
        ("포트",   "80"),
    ]
    for j, (k, v) in enumerate(in_lines):
        by = ib_y + Inches(0.4) + j * Inches(0.42)
        rect(sl, ox, by, Inches(1.3), Inches(0.42),
             fill=RGBColor(0x3a, 0x0c, 0x0c))
        txt(sl, k, ox + Inches(0.1), by + Inches(0.05),
            Inches(1.2), Inches(0.34), size=11, bold=True, color=RED)
        txt(sl, v, ox + Inches(1.35), by + Inches(0.05),
            pw - Inches(1.4), Inches(0.34), size=11, color=WHITE)

fw_panel(sl, Inches(0.4), "🔷  스테이지 (개발 서버)",
         MBLUE,
         "203.254.214.131",
         "openapi.stage.samsung.net",
         "112.106.197.162  (1개)")

fw_panel(sl, Inches(6.93), "🔶  운영 (실사용 서버)",
         RGBColor(0x5c, 0x35, 0x05),
         "112.107.220.134",
         "openapi.samsung.net",
         "182.195.35.14\n182.195.35.15\n182.195.35.16  (3개)")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — STEP 03: Knox 서버에 등록하기
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 03", "Knox 수/발신 서버에 등록하기",
       "봇을 Knox 서버에 등록하면 System ID와 Access Token이 발급됩니다 (본인만 봇 앱 리스트 확인 가능)")

# 좌: 스테이지
lx = Inches(0.4)
rect(sl, lx, Inches(1.65), Inches(6.1), Inches(0.42), fill=MBLUE)
txt(sl, "  🔷  스테이지 봇 연계 신청",
    lx, Inches(1.65), Inches(6.1), Inches(0.42), size=13, bold=True, color=WHITE)

path_box(sl, lx, Inches(2.12), Inches(6.1),
         "Home → My Interface → Bot → 연계 신청관리 → 스테이지 봇 연계 신청")

st_items = [
    ("결재",            "그룹장"),
    ("합의",            "없음"),
    ("AI빌더 사용여부", "미사용  (AI빌더 서버 주소가 달라 신중히 선택)"),
    ("과금 관리자",     "본인"),
]
for j, (k, v) in enumerate(st_items):
    by = Inches(2.72) + j * Inches(0.5)
    txt(sl, f"• {k}:", lx + Inches(0.2), by, Inches(1.9), Inches(0.45),
        size=12, bold=True, color=ACCENT)
    txt(sl, v, lx + Inches(2.15), by, Inches(4.2), Inches(0.45),
        size=12, color=WHITE)

photo_box(sl, lx, Inches(4.78), Inches(6.1), Inches(2.35),
          "스테이지 봇 연계 신청 화면 캡쳐")

# 우: 운영
rx = Inches(6.9)
rect(sl, rx, Inches(1.65), Inches(6.1), Inches(0.42),
     fill=RGBColor(0x5c, 0x35, 0x05))
txt(sl, "  🔶  운영 봇 연계 신청",
    rx, Inches(1.65), Inches(6.1), Inches(0.42), size=13, bold=True, color=WHITE)

path_box(sl, rx, Inches(2.12), Inches(6.1),
         "Home → My Interface → Bot → 연계 신청관리 → 운영 봇 연계 신청")

op_items = [
    ("AI빌더 사용여부", "미사용  (AI빌더 서버 주소가 달라 신중히 선택)"),
    ("과금 관리자",     "본인"),
]
for j, (k, v) in enumerate(op_items):
    by = Inches(2.72) + j * Inches(0.5)
    txt(sl, f"• {k}:", rx + Inches(0.2), by, Inches(1.9), Inches(0.45),
        size=12, bold=True, color=ORANGE)
    txt(sl, v, rx + Inches(2.15), by, Inches(4.2), Inches(0.45),
        size=12, color=WHITE)

note_box(sl, rx, Inches(3.8), Inches(6.1),
         "⚠  등록 완료 시 System ID 와 Access Token 을 꼭 보관하세요", color=ORANGE)

photo_box(sl, rx, Inches(4.42), Inches(6.1), Inches(2.7),
          "운영 봇 연계 신청 화면 캡쳐")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — STEP 04: API 연결 & 챗봇 방 생성
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 04", "API 연결 & 챗봇 방 생성",
       "Knox Developer Center의 API 문서를 참고하여 챗봇 대화방을 생성합니다")

path_box(sl, Inches(0.4), Inches(1.65), W - Inches(0.8),
         "Home  →  Dev Guide  →  메신저   또는   Home  →  Dev Guide  →  Bot  →  시작하기")

# 좌: 절차
lx = Inches(0.4)
steps_4 = [
    ("①", "메신저 Device 등록",
     "봇 계정에 Device를 등록합니다.\nSystem ID 와 Access Token 을 사용합니다."),
    ("②", "대화방 생성",
     "등록된 Device 로 챗봇 대화방을 생성합니다."),
    ("③", "API 문서 확인 및 연동",
     "Messenger API 문서를 참고하여\n발신/수신 API 를 개발 서버에 연결합니다."),
]
for j, (num, title_s, desc) in enumerate(steps_4):
    by = Inches(2.3) + j * Inches(1.45)
    rect(sl, lx, by, Inches(5.9), Inches(1.3), fill=BLUE)
    rect(sl, lx, by, Inches(5.9), Inches(0.08), fill=ACCENT)
    txt(sl, num, lx + Inches(0.1), by + Inches(0.1),
        Inches(0.6), Inches(0.55), size=22, bold=True, color=ACCENT)
    txt(sl, title_s, lx + Inches(0.75), by + Inches(0.1),
        Inches(5.0), Inches(0.45), size=14, bold=True, color=WHITE)
    txt(sl, desc, lx + Inches(0.75), by + Inches(0.55),
        Inches(5.0), Inches(0.7), size=11, color=LBLUE)

note_box(sl, lx, Inches(6.68), Inches(5.9),
         "📎 API 문서: Developer Center에서 Messenger API 문서를 첨부하세요", color=ACCENT)

# 우: 캡쳐 박스
photo_box(sl, Inches(6.7), Inches(2.3), Inches(6.3), Inches(4.9),
          "Dev Guide 화면 캡쳐")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — STEP 05: FAQ
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
header(sl, "STEP 05", "FAQ",
       "궁금한 점이 있을 때 참고하세요")

faq = [
    ("Q1", "문의는 어디에 하나요?",
     "Knoxportal@samsung.com 으로 이메일 문의"),
    ("Q2", "Knox Support는 어떻게 사용하나요?",
     "Knox Portal 화면 내 프로필 왼편  ❓  → Knox Support 진입\n"
     "Teams 메뉴에서 검색 및 문의 업로드 가능"),
]

for j, (num, q, a) in enumerate(faq):
    by = Inches(1.75) + j * Inches(1.8)
    bw2 = Inches(6.2)
    rect(sl, Inches(0.4), by, bw2, Inches(1.55), fill=BLUE)
    rect(sl, Inches(0.4), by, bw2, Inches(0.08), fill=ACCENT)
    rect(sl, Inches(0.4), by + Inches(0.12), Inches(0.6), Inches(0.55),
         fill=MBLUE)
    txt(sl, num, Inches(0.4), by + Inches(0.12), Inches(0.6), Inches(0.52),
        size=13, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    txt(sl, q, Inches(1.1), by + Inches(0.12), bw2 - Inches(0.75), Inches(0.52),
        size=14, bold=True, color=WHITE)
    txt(sl, a, Inches(1.1), by + Inches(0.7), bw2 - Inches(0.75), Inches(0.75),
        size=12, color=LBLUE)

photo_box(sl, Inches(7.1), Inches(1.75), Inches(5.9), Inches(5.3),
          "Knox Support 화면 캡쳐")

txt(sl, "Knoxportal@samsung.com",
    Inches(0.5), Inches(5.5), Inches(6.0), Inches(0.5),
    size=14, bold=True, color=ACCENT)

note_box(sl, Inches(0.4), Inches(6.1), Inches(6.5),
         "💡 Knox Portal 내 물음표(?) 버튼 → Knox Support → Teams 메뉴", color=LBLUE)


# ══════════════════════════════════════════════════════════════════════════════
# 저장
# ══════════════════════════════════════════════════════════════════════════════
out = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knox_chatbot_가이드.pptx"
)
prs.save(out)
print(f"저장 완료: {out}")
