"""
FA 빅데이터 분석 챗봇 서비스 - 보고서 PPT (1~2장)
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

SAMSUNG_BLUE  = RGBColor(0x1E, 0x3A, 0x5F)
SAMSUNG_MID   = RGBColor(0x2D, 0x5A, 0x9E)
ACCENT        = RGBColor(0x00, 0x78, 0xD4)
GREEN         = RGBColor(0x10, 0x7C, 0x10)
ORANGE        = RGBColor(0xD8, 0x3B, 0x01)
PURPLE        = RGBColor(0x60, 0x50, 0xA0)
WHITE         = RGBColor(0xFF, 0xFF, 0xFF)
GRAY          = RGBColor(0x55, 0x55, 0x55)
LIGHT         = RGBColor(0xF0, 0xF4, 0xFA)
LGRAY         = RGBColor(0xE0, 0xE8, 0xF0)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
W = prs.slide_width
H = prs.slide_height
BLANK = prs.slide_layouts[6]


def rect(slide, l, t, w, h, fill=None, line=None, lw=Pt(0.75)):
    s = slide.shapes.add_shape(1, l, t, w, h)
    if fill: s.fill.solid(); s.fill.fore_color.rgb = fill
    else:    s.fill.background()
    if line: s.line.color.rgb = line; s.line.width = lw
    else:    s.line.fill.background()
    return s

def rbox(slide, l, t, w, h, text, fill=ACCENT, fc=WHITE, sz=11, bold=True, align=PP_ALIGN.CENTER):
    s = slide.shapes.add_shape(5, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = fill
    s.line.fill.background()
    tf = s.text_frame; tf.word_wrap = True
    p  = tf.paragraphs[0]; p.alignment = align
    r  = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = bold; r.font.color.rgb = fc
    return s

def txt(slide, text, l, t, w, h, sz=10, bold=False, color=None, align=PP_ALIGN.LEFT, italic=False):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    p  = tf.paragraphs[0]; p.alignment = align
    r  = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = bold; r.font.italic = italic
    r.font.color.rgb = color or RGBColor(0x1A, 0x1A, 0x1A)
    return tb

def arrow_r(slide, l, t, w=Cm(0.9), h=Cm(0.5), color=SAMSUNG_MID):
    s = slide.shapes.add_shape(13, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background()

def arrow_d(slide, l, t, w=Cm(0.5), h=Cm(0.7), color=SAMSUNG_MID):
    s = slide.shapes.add_shape(2, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background()


# ════════════════════════════════════════════════════════════════════════════
# [1] 핵심 보고 슬라이드 (1장 요약)
# ════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, W, H, fill=WHITE)

# ── 상단 헤더 ────────────────────────────────────────────────────────────────
rect(slide, 0, 0, W, Cm(1.9), fill=SAMSUNG_BLUE)
rect(slide, 0, 0, Cm(0.4), Cm(1.9), fill=ACCENT)
txt(slide, "Field Analysis 빅데이터 분석 챗봇 서비스 자동화",
    Cm(0.8), Cm(0.15), W * 0.65, Cm(0.9), sz=18, bold=True, color=WHITE)
txt(slide, "(주)삼성전자서비스  |  2025",
    Cm(0.8), Cm(1.0), W * 0.5, Cm(0.7), sz=10, color=RGBColor(0xBB, 0xCC, 0xEE))
txt(slide, "24/7 FA 분석 자동화 체계 구축",
    W * 0.68, Cm(0.45), W * 0.31, Cm(0.8), sz=12, bold=True,
    color=RGBColor(0x88, 0xBB, 0xFF), align=PP_ALIGN.RIGHT)

# ── 섹션 A: 추진 배경 (좌상) ────────────────────────────────────────────────
SEC_TOP = Cm(2.1)
COL1_W  = W * 0.28
COL2_W  = W * 0.40
COL3_W  = W - COL1_W - COL2_W - Cm(0.5)
GAP     = Cm(0.18)
COL1_L  = Cm(0.3)
COL2_L  = COL1_L + COL1_W + GAP
COL3_L  = COL2_L + COL2_W + GAP

# 섹션 헤더
for l, w, label, col in [
    (COL1_L, COL1_W, "📋 추진 배경", SAMSUNG_BLUE),
    (COL2_L, COL2_W, "⚙️ 시스템 구성",  ACCENT),
    (COL3_L, COL3_W, "✅ 주요 기능 & 기대 효과", GREEN),
]:
    rect(slide, l, SEC_TOP, w, Cm(0.55), fill=col)
    txt(slide, label, l + Cm(0.15), SEC_TOP + Cm(0.07), w - Cm(0.2), Cm(0.44),
        sz=11, bold=True, color=WHITE)

BODY_TOP = SEC_TOP + Cm(0.58)
BODY_H   = H - BODY_TOP - Cm(0.9)

# ── 추진 배경 내용 ───────────────────────────────────────────────────────────
rect(slide, COL1_L, BODY_TOP, COL1_W, BODY_H, fill=LIGHT, line=LGRAY)

# 현황
rect(slide, COL1_L + Cm(0.15), BODY_TOP + Cm(0.12), COL1_W - Cm(0.3), Cm(0.38), fill=ORANGE)
txt(slide, "현  황", COL1_L + Cm(0.25), BODY_TOP + Cm(0.15), COL1_W - Cm(0.3), Cm(0.32),
    sz=9.5, bold=True, color=WHITE)
issues = [
    "FA 현장 방문 전 빅데이터 분석 결과\n사전 공유로 체계적 대응 지원",
    "통신사 이관 이슈 조기 분류 →\n진성 단말 이슈 집중 가능",
]
for i, s in enumerate(issues):
    txt(slide, f"• {s}", COL1_L + Cm(0.2), BODY_TOP + Cm(0.6) + i * Cm(0.85),
        COL1_W - Cm(0.3), Cm(0.85), sz=9)

# 문제점
rect(slide, COL1_L + Cm(0.15), BODY_TOP + Cm(2.45), COL1_W - Cm(0.3), Cm(0.38), fill=RGBColor(0xC0, 0x20, 0x20))
txt(slide, "문제점", COL1_L + Cm(0.25), BODY_TOP + Cm(2.48), COL1_W - Cm(0.3), Cm(0.32),
    sz=9.5, bold=True, color=WHITE)
probs = ["주말/야간 대응 불가", "수동 조회 대기시간 발생", "본사 인력 비효율"]
for i, s in enumerate(probs):
    txt(slide, f"⚠ {s}", COL1_L + Cm(0.2), BODY_TOP + Cm(2.95) + i * Cm(0.68),
        COL1_W - Cm(0.3), Cm(0.65), sz=9, color=RGBColor(0xC0, 0x20, 0x20), bold=True)

# 목표
rect(slide, COL1_L + Cm(0.15), BODY_TOP + Cm(5.02), COL1_W - Cm(0.3), Cm(0.38), fill=SAMSUNG_MID)
txt(slide, "개선 목표", COL1_L + Cm(0.25), BODY_TOP + Cm(5.05), COL1_W - Cm(0.3), Cm(0.32),
    sz=9.5, bold=True, color=WHITE)
goals = ["챗봇 기반 24/7 자동 분석", "VOC 해결율 향상", "FA 대응 비용 절감"]
for i, s in enumerate(goals):
    txt(slide, f"▶ {s}", COL1_L + Cm(0.2), BODY_TOP + Cm(5.5) + i * Cm(0.6),
        COL1_W - Cm(0.3), Cm(0.58), sz=9, color=SAMSUNG_BLUE, bold=True)

# ── 시스템 구성 (중앙, 도형) ────────────────────────────────────────────────
rect(slide, COL2_L, BODY_TOP, COL2_W, BODY_H, fill=LIGHT, line=LGRAY)

BW = Cm(3.6); BH = Cm(0.85)
CX = COL2_L + COL2_W / 2

def cx_box(slide, t, text, fill):
    l = CX - BW / 2
    rbox(slide, l, t, BW, BH, text, fill=fill, sz=10)
    return l

# FA 담당자
cx_box(slide, BODY_TOP + Cm(0.25), "👤 FA 담당자 (Knox Messenger)", SAMSUNG_BLUE)

# SN 입력 → ↓
arrow_d(slide, CX - Cm(0.25), BODY_TOP + Cm(1.2), color=ACCENT)
txt(slide, "SN 입력", CX + Cm(0.35), BODY_TOP + Cm(1.25), Cm(1.8), Cm(0.4), sz=8, color=ACCENT, bold=True)

# Knox Messenger
cx_box(slide, BODY_TOP + Cm(2.0), "💬 Knox Messenger", RGBColor(0x00, 0x80, 0x00))

arrow_d(slide, CX - Cm(0.25), BODY_TOP + Cm(2.95), color=SAMSUNG_MID)
txt(slide, "Webhook", CX + Cm(0.35), BODY_TOP + Cm(3.0), Cm(1.8), Cm(0.4), sz=8, color=SAMSUNG_MID)

# FA 챗봇 서비스
cx_box(slide, BODY_TOP + Cm(3.75), "⚙️ FA 챗봇 서비스 (FastAPI)", ACCENT)

arrow_d(slide, CX - Cm(0.25), BODY_TOP + Cm(4.7), color=PURPLE)
txt(slide, "자동 조회", CX + Cm(0.35), BODY_TOP + Cm(4.75), Cm(1.8), Cm(0.4), sz=8, color=PURPLE)

# 빅데이터 포털
cx_box(slide, BODY_TOP + Cm(5.5), "🗄️ 삼성 빅데이터 포털", PURPLE)

# ← 결과 반환 선 (포털→챗봇→Knox→FA 역방향 표시)
txt(slide, "← 분석결과 자동 전송", COL2_L + Cm(0.2), BODY_TOP + Cm(4.35), COL2_W - Cm(0.3), Cm(0.4),
    sz=8, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
txt(slide, "← PDF/리포트 자동 생성·전달", COL2_L + Cm(0.2), BODY_TOP + Cm(3.35), COL2_W - Cm(0.3), Cm(0.4),
    sz=8, color=GREEN, bold=True, align=PP_ALIGN.CENTER)

# ── 주요 기능 & 기대 효과 (우측) ────────────────────────────────────────────
rect(slide, COL3_L, BODY_TOP, COL3_W, BODY_H, fill=LIGHT, line=LGRAY)

feats = [
    (SAMSUNG_BLUE, "SN 기반 자동 분석",    "Knox Messenger 챗봇으로 SN 입력\nAdaptive Card UI · 다중 SN 지원"),
    (ACCENT,       "빅데이터 자동 조회",    "포털 자동 로그인·조회 (Playwright)\n병렬 처리로 분석 속도 최적화"),
    (GREEN,        "분석 리포트 자동 전송", "PDF/HTML 리포트 자동 생성\nKnox Messenger로 즉시 전달"),
    (PURPLE,       "24/7 무인 대응",        "주말·야간 자동 처리\n오류 알림 · 타임아웃 자동 처리"),
]
for i, (col, title, desc) in enumerate(feats):
    ty = BODY_TOP + Cm(0.15) + i * Cm(1.75)
    rect(slide, COL3_L + Cm(0.15), ty, COL3_W - Cm(0.3), Cm(1.6),
         fill=WHITE, line=col, lw=Pt(1.2))
    rect(slide, COL3_L + Cm(0.15), ty, Cm(0.25), Cm(1.6), fill=col)
    txt(slide, title, COL3_L + Cm(0.55), ty + Cm(0.1), COL3_W - Cm(0.7), Cm(0.45),
        sz=10, bold=True, color=col)
    txt(slide, desc, COL3_L + Cm(0.55), ty + Cm(0.55), COL3_W - Cm(0.7), Cm(1.0),
        sz=9, color=GRAY)

# 기대 효과
eff_y = BODY_TOP + Cm(7.1)
effs = [("VOC 해결율↑", SAMSUNG_BLUE), ("대기시간 제거", ACCENT), ("FA 비용↓", GREEN)]
ew = (COL3_W - Cm(0.3)) / 3
for i, (label, col) in enumerate(effs):
    el = COL3_L + Cm(0.15) + i * (ew + Cm(0.05))
    rect(slide, el, eff_y, ew, Cm(0.5), fill=col)
    txt(slide, label, el, eff_y + Cm(0.05), ew, Cm(0.4),
        sz=9, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# ── 하단 푸터 ────────────────────────────────────────────────────────────────
rect(slide, 0, H - Cm(0.75), W, Cm(0.75), fill=SAMSUNG_BLUE)
txt(slide, "Samsung Electronics Service  |  Field Analysis 챗봇 자동화  |  2025",
    Cm(0.5), H - Cm(0.7), W * 0.7, Cm(0.65), sz=8.5, color=RGBColor(0xAA, 0xBB, 0xCC))
txt(slide, "Confidential", W - Cm(2.5), H - Cm(0.7), Cm(2.2), Cm(0.65),
    sz=9, bold=True, color=WHITE, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════════════════
# 저장
# ════════════════════════════════════════════════════════════════════════════
out = "/home/user/FA-service/FA_챗봇_보고서.pptx"
prs.save(out)
print(f"저장 완료: {out}")
