"""
FA 빅데이터 분석 챗봇 서비스 - 보고서 PPT (1장, 세련된 미니멀 디자인)
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY   = RGBColor(0x1C, 0x3A, 0x5F)   # 남색
DGRAY  = RGBColor(0x40, 0x40, 0x40)   # 진회색 (본문)
MGRAY  = RGBColor(0x88, 0x88, 0x88)   # 중간 회색 (부제·캡션)
LGRAY  = RGBColor(0xD8, 0xD8, 0xD8)   # 연회색 (선·구분)
XLGRAY = RGBColor(0xF5, 0xF5, 0xF5)   # 매우 연한 배경
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
W = prs.slide_width
H = prs.slide_height
BLANK = prs.slide_layouts[6]


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────
def rect(slide, l, t, w, h, fill=None, line_rgb=None, lw=Pt(0.5)):
    s = slide.shapes.add_shape(1, l, t, w, h)
    if fill: s.fill.solid(); s.fill.fore_color.rgb = fill
    else:    s.fill.background()
    if line_rgb: s.line.color.rgb = line_rgb; s.line.width = lw
    else:        s.line.fill.background()
    return s

def txt(slide, text, l, t, w, h, sz=10, bold=False, color=None,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = wrap
    p  = tf.paragraphs[0]; p.alignment = align
    r  = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = bold; r.font.italic = italic
    r.font.color.rgb = color or DGRAY
    return tb

def flow_box(slide, l, t, w, h, label, sublabel=""):
    """흐름도용 박스 - 흰 배경, 남색 얇은 테두리"""
    rect(slide, l, t, w, h, fill=WHITE, line_rgb=NAVY, lw=Pt(0.8))
    if sublabel:
        txt(slide, label, l, t + Cm(0.08), w, Cm(0.5),
            sz=9.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        txt(slide, sublabel, l, t + Cm(0.55), w, Cm(0.4),
            sz=8, color=MGRAY, align=PP_ALIGN.CENTER)
    else:
        txt(slide, label, l, t + Cm(0.12), w, h - Cm(0.1),
            sz=9.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)

def arrow_d(slide, cx, t, h=Cm(0.5)):
    """아래 화살표"""
    s = slide.shapes.add_shape(2, cx - Cm(0.18), t, Cm(0.36), h)
    s.fill.solid(); s.fill.fore_color.rgb = MGRAY; s.line.fill.background()

def divider(slide, l, t, w):
    rect(slide, l, t, w, Cm(0.02), fill=LGRAY)

def section_title(slide, l, t, w, text):
    """섹션 제목: 남색 좌측 바 + 텍스트"""
    rect(slide, l, t + Cm(0.05), Cm(0.18), Cm(0.55), fill=NAVY)
    txt(slide, text, l + Cm(0.3), t, w - Cm(0.3), Cm(0.65),
        sz=10.5, bold=True, color=NAVY)


# ════════════════════════════════════════════════════════════════════════════
# 슬라이드 1장
# ════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, W, H, fill=WHITE)

# ── 상단 남색 헤더 ────────────────────────────────────────────────────────────
HEADER_H = Cm(1.6)
rect(slide, 0, 0, W, HEADER_H, fill=NAVY)
txt(slide, "Field Analysis 빅데이터 분석 챗봇 서비스 자동화",
    Cm(0.7), Cm(0.18), W * 0.68, Cm(0.85), sz=18, bold=True, color=WHITE)
txt(slide, "(주)삼성전자서비스",
    Cm(0.7), Cm(0.97), W * 0.4, Cm(0.5), sz=9.5, color=RGBColor(0xB0, 0xBE, 0xD4))
txt(slide, "2025",
    W - Cm(2.2), Cm(0.97), Cm(1.8), Cm(0.5), sz=9.5,
    color=RGBColor(0xB0, 0xBE, 0xD4), align=PP_ALIGN.RIGHT)

# ── 레이아웃 정의 ────────────────────────────────────────────────────────────
BODY_T = HEADER_H + Cm(0.25)
BODY_H_ = H - HEADER_H - Cm(0.25) - Cm(0.6)   # 하단 푸터 제외

GAP    = Cm(0.3)
C1_W   = W * 0.26
C2_W   = W * 0.36
C3_W   = W - C1_W - C2_W - GAP * 2 - Cm(0.6)
C1_L   = Cm(0.3)
C2_L   = C1_L + C1_W + GAP
C3_L   = C2_L + C2_W + GAP

# 세로 구분선
rect(slide, C2_L - GAP * 0.5, BODY_T, Cm(0.02), BODY_H_, fill=LGRAY)
rect(slide, C3_L - GAP * 0.5, BODY_T, Cm(0.02), BODY_H_, fill=LGRAY)


# ════════════════════════════════════════════════════════════════════════════
# 컬럼 1: 추진 배경
# ════════════════════════════════════════════════════════════════════════════
cy = BODY_T + Cm(0.1)
section_title(slide, C1_L, cy, C1_W, "추진 배경")
cy += Cm(0.7)

paras = [
    "서비스센터 고객 VOC 발생 시 FA가 현장 방문하여 문제 해결 지원",
    "빅데이터 분석 결과를 사전 공유, 통신사 이관 이슈 조기 분류 →진성 단말 이슈에 집중",
]
for p in paras:
    txt(slide, f"• {p}", C1_L + Cm(0.2), cy, C1_W - Cm(0.2), Cm(0.9), sz=9, color=DGRAY)
    cy += Cm(0.92)

cy += Cm(0.15)
divider(slide, C1_L, cy, C1_W)
cy += Cm(0.2)
section_title(slide, C1_L, cy, C1_W, "현황 및 문제점")
cy += Cm(0.7)

problems = [
    ("주말·야간 대응 불가", "본사 인력 부재 시 분석 지원 중단"),
    ("수동 조회 대기시간", "빅데이터 수동 조회로 현장 대응 지연"),
    ("인력 비효율",         "반복 단순업무로 핵심 업무 집중 저하"),
]
for title, desc in problems:
    txt(slide, title, C1_L + Cm(0.2), cy, C1_W - Cm(0.2), Cm(0.4),
        sz=9, bold=True, color=DGRAY)
    txt(slide, desc,  C1_L + Cm(0.2), cy + Cm(0.37), C1_W - Cm(0.2), Cm(0.4),
        sz=8.5, color=MGRAY, italic=True)
    cy += Cm(0.85)

cy += Cm(0.15)
divider(slide, C1_L, cy, C1_W)
cy += Cm(0.2)
section_title(slide, C1_L, cy, C1_W, "개선 목표")
cy += Cm(0.7)

goals = [
    "챗봇 기반 24/7 자동 분석 체계 구축",
    "고객 VOC 해결율 향상",
    "본사 업무 효율성 제고",
    "FA 대응 비용 절감",
]
for g in goals:
    txt(slide, f"▸  {g}", C1_L + Cm(0.2), cy, C1_W - Cm(0.2), Cm(0.5),
        sz=9, color=DGRAY)
    cy += Cm(0.5)


# ════════════════════════════════════════════════════════════════════════════
# 컬럼 2: 시스템 구성 (단방향 흐름, 위→아래)
# ════════════════════════════════════════════════════════════════════════════
cy2 = BODY_T + Cm(0.1)
section_title(slide, C2_L, cy2, C2_W, "시스템 구성")
cy2 += Cm(0.75)

BW = C2_W - Cm(0.8)
BH = Cm(0.82)
CX = C2_L + C2_W / 2
BL = CX - BW / 2

ARROW_GAP = Cm(0.42)

def fbox(t, label, sub=""):
    flow_box(slide, BL, t, BW, BH, label, sub)
    return t + BH

def farrow(t, label=""):
    arrow_d(slide, CX, t, Cm(ARROW_GAP))
    if label:
        txt(slide, label, CX + Cm(0.28), t + Cm(0.05), Cm(1.8), Cm(0.32),
            sz=7.5, color=MGRAY)
    return t + ARROW_GAP

# 흐름: FA → Knox → 챗봇 → 포털 → 결과 → Knox(수신) → FA(결과확인)
cy2 = fbox(cy2, "👤  FA 담당자",      "SN 입력 요청")
cy2 = farrow(cy2, "SN 입력")
cy2 = fbox(cy2, "💬  Knox Messenger", "메시지 전달")
cy2 = farrow(cy2, "Webhook 수신")
cy2 = fbox(cy2, "⚙  FA 챗봇 서비스", "FastAPI 서버")
cy2 = farrow(cy2, "자동 조회")
cy2 = fbox(cy2, "🗄  빅데이터 포털",  "자동 로그인·조회")
cy2 = farrow(cy2, "결과 반환")
cy2 = fbox(cy2, "📄  분석 결과 생성", "PDF / HTML 리포트")
cy2 = farrow(cy2, "자동 전송")
cy2 = fbox(cy2, "💬  Knox Messenger", "결과 메시지 수신")
cy2 = farrow(cy2, "알림 수신")
fbox(cy2,        "👤  FA 담당자",      "현장 대응 준비")


# ════════════════════════════════════════════════════════════════════════════
# 컬럼 3: 주요 기능 & 기대 효과
# ════════════════════════════════════════════════════════════════════════════
cy3 = BODY_T + Cm(0.1)
section_title(slide, C3_L, cy3, C3_W, "주요 기능")
cy3 += Cm(0.7)

features = [
    ("SN 기반 자동 분석",    "Knox Messenger 챗봇으로 SN 입력\nAdaptive Card UI · 다중 SN 동시 지원"),
    ("빅데이터 자동 조회",   "포털 자동 로그인·조회 (Playwright)\n병렬 처리로 속도 최적화"),
    ("분석 리포트 자동 전송","PDF·HTML 리포트 자동 생성\nKnox Messenger로 즉시 전달"),
    ("24/7 무인 대응",       "주말·야간 무인 자동 처리\n오류 알림·타임아웃 자동 처리"),
]
for i, (title, desc) in enumerate(features):
    # 좌측 회색 세로선 포인트
    rect(slide, C3_L + Cm(0.15), cy3 + Cm(0.1), Cm(0.1), Cm(0.5), fill=LGRAY)
    txt(slide, title, C3_L + Cm(0.4), cy3 + Cm(0.05), C3_W - Cm(0.45), Cm(0.45),
        sz=9.5, bold=True, color=DGRAY)
    txt(slide, desc, C3_L + Cm(0.4), cy3 + Cm(0.48), C3_W - Cm(0.45), Cm(0.7),
        sz=8.5, color=MGRAY)
    cy3 += Cm(1.28)
    if i < len(features) - 1:
        divider(slide, C3_L + Cm(0.15), cy3, C3_W - Cm(0.15))
        cy3 += Cm(0.1)

cy3 += Cm(0.2)
divider(slide, C3_L, cy3, C3_W)
cy3 += Cm(0.25)
section_title(slide, C3_L, cy3, C3_W, "기대 효과")
cy3 += Cm(0.75)

effects = [
    "고객 VOC 해결율 향상 (24/7 즉각 대응)",
    "본사 분석 인력 업무 효율 제고",
    "FA 현장 대응 비용 절감",
    "서비스센터 FA 이관 이슈 사전 분류",
]
for e in effects:
    txt(slide, f"▸  {e}", C3_L + Cm(0.2), cy3, C3_W - Cm(0.2), Cm(0.45),
        sz=9, color=DGRAY)
    cy3 += Cm(0.47)

# ── 하단 푸터 ────────────────────────────────────────────────────────────────
FOOTER_T = H - Cm(0.55)
rect(slide, 0, FOOTER_T, W, Cm(0.55), fill=NAVY)
txt(slide, "Samsung Electronics Service  ·  Field Analysis Chatbot Automation  ·  2025",
    Cm(0.6), FOOTER_T + Cm(0.1), W * 0.75, Cm(0.38), sz=8, color=RGBColor(0xA0, 0xB2, 0xCC))
txt(slide, "Confidential", W - Cm(2.3), FOOTER_T + Cm(0.1), Cm(2.0), Cm(0.38),
    sz=8, bold=True, color=WHITE, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════════════════
out = "/home/user/FA-service/FA_챗봇_보고서.pptx"
prs.save(out)
print(f"저장 완료: {out}")
