"""
FA 빅데이터 분석 챗봇 서비스 - 보고서 PPT (1장)
상단: 추진배경 / 문제점 / 개선목표 (3단 텍스트)
하단: 시스템 구성 (흐름도) + 주요 기능 (우측)
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY   = RGBColor(0x1C, 0x3A, 0x5F)
DGRAY  = RGBColor(0x40, 0x40, 0x40)
MGRAY  = RGBColor(0x88, 0x88, 0x88)
LGRAY  = RGBColor(0xD8, 0xD8, 0xD8)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
W = prs.slide_width
H = prs.slide_height
BLANK = prs.slide_layouts[6]


def rect(slide, l, t, w, h, fill=None, line_rgb=None, lw=Pt(0.5)):
    s = slide.shapes.add_shape(1, l, t, w, h)
    if fill: s.fill.solid(); s.fill.fore_color.rgb = fill
    else:    s.fill.background()
    if line_rgb: s.line.color.rgb = line_rgb; s.line.width = lw
    else:        s.line.fill.background()
    return s

def txt(slide, text, l, t, w, h, sz=10, bold=False, color=None,
        align=PP_ALIGN.LEFT, italic=False):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    p  = tf.paragraphs[0]; p.alignment = align
    r  = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = bold; r.font.italic = italic
    r.font.color.rgb = color or DGRAY
    return tb

def section_title(slide, l, t, w, text):
    rect(slide, l, t + Cm(0.07), Cm(0.16), Cm(0.5), fill=NAVY)
    txt(slide, text, l + Cm(0.3), t, w, Cm(0.62), sz=10.5, bold=True, color=NAVY)

def divider_v(slide, l, t, h):
    rect(slide, l, t, Cm(0.02), h, fill=LGRAY)

def divider_h(slide, l, t, w):
    rect(slide, l, t, w, Cm(0.02), fill=LGRAY)

def flow_node(slide, l, t, w, h, top_text, bot_text=""):
    rect(slide, l, t, w, h, fill=WHITE, line_rgb=NAVY, lw=Pt(0.75))
    if bot_text:
        txt(slide, top_text, l, t + Cm(0.08), w, Cm(0.45),
            sz=8.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        txt(slide, bot_text, l, t + Cm(0.5), w, Cm(0.38),
            sz=7.5, color=MGRAY, align=PP_ALIGN.CENTER)
    else:
        txt(slide, top_text, l, t + Cm(0.12), w, h,
            sz=8.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)

def arrow_r(slide, l, t, w=Cm(0.55), h=Cm(0.35)):
    s = slide.shapes.add_shape(13, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = LGRAY
    s.line.fill.background()


# ════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
rect(slide, 0, 0, W, H, fill=WHITE)

# ── 헤더 ─────────────────────────────────────────────────────────────────────
HH = Cm(1.55)
rect(slide, 0, 0, W, HH, fill=NAVY)
txt(slide, "Field Analysis 빅데이터 분석 챗봇 서비스 자동화",
    Cm(0.7), Cm(0.15), W * 0.72, Cm(0.85), sz=18, bold=True, color=WHITE)
txt(slide, "(주)삼성전자서비스  ·  2025",
    Cm(0.7), Cm(0.98), W * 0.5, Cm(0.45), sz=9, color=RGBColor(0xA8, 0xBA, 0xD2))

PAD = Cm(0.3)

# ════════════════════════════════════════════════════════════════════════════
# 상단: 추진배경 / 문제점 / 개선목표 (3단)
# ════════════════════════════════════════════════════════════════════════════
TOP_T = HH + Cm(0.2)
TOP_H = Cm(3.1)
GAP   = Cm(0.3)
CW    = (W - PAD * 2 - GAP * 2) / 3
C1L   = PAD
C2L   = C1L + CW + GAP
C3L   = C2L + CW + GAP

divider_v(slide, C2L - GAP / 2, TOP_T, TOP_H)
divider_v(slide, C3L - GAP / 2, TOP_T, TOP_H)

# 추진 배경
cy = TOP_T
section_title(slide, C1L, cy, CW, "추진 배경")
cy += Cm(0.65)
for p in [
    "서비스센터 고객 VOC 발생 시 FA가 현장 방문, 빅데이터 분석 결과를 사전 공유하여 체계적 대응 지원",
    "통신사 이관 이슈 조기 분류 → 진성 단말 이슈에 집중",
]:
    txt(slide, f"• {p}", C1L + Cm(0.15), cy, CW - Cm(0.15), Cm(0.82), sz=9)
    cy += Cm(0.85)

cy += Cm(0.1)
section_title(slide, C1L, cy, CW, "문제점")
cy += Cm(0.65)
for p in ["주말·야간 대응 불가  (본사 인력 부재)",
          "수동 조회로 현장 대응 지연",
          "반복 업무로 인력 비효율"]:
    txt(slide, f"• {p}", C1L + Cm(0.15), cy, CW - Cm(0.15), Cm(0.42), sz=9)
    cy += Cm(0.43)

# 개선 목표
cy = TOP_T
section_title(slide, C2L, cy, CW, "개선 목표")
cy += Cm(0.65)
for g in ["챗봇 기반 24/7 자동 분석 체계 구축",
          "고객 VOC 해결율 향상",
          "본사 업무 효율성 제고",
          "FA 대응 비용 절감",
          "서비스센터 FA 이관 이슈 사전 분류"]:
    txt(slide, f"▸  {g}", C2L + Cm(0.15), cy, CW - Cm(0.15), Cm(0.46), sz=9)
    cy += Cm(0.48)

# 기대 효과
cy = TOP_T
section_title(slide, C3L, cy, CW, "기대 효과")
cy += Cm(0.65)
for e in ["FA 현장 대응 속도 향상  (즉각 분석 결과 제공)",
          "본사 분석 인력 업무 부담 경감",
          "야간·주말 고객 불만 최소화",
          "체계적 이슈 분류로 FA 출동 비용 절감"]:
    txt(slide, f"▸  {e}", C3L + Cm(0.15), cy, CW - Cm(0.15), Cm(0.46), sz=9)
    cy += Cm(0.48)

# ── 상·하단 구분선 ─────────────────────────────────────────────────────────
DIV_Y = TOP_T + TOP_H + Cm(0.15)
divider_h(slide, PAD, DIV_Y, W - PAD * 2)

# ════════════════════════════════════════════════════════════════════════════
# 하단: 시스템 구성 (좌) + 주요 기능 (우)
# ════════════════════════════════════════════════════════════════════════════
BOT_T    = DIV_Y + Cm(0.12)
BOT_H    = H - BOT_T - Cm(0.6)
FLOW_W   = W * 0.67
FEAT_W   = W - FLOW_W - PAD * 2 - Cm(0.15)
FEAT_L   = PAD + FLOW_W + Cm(0.15)

divider_v(slide, FEAT_L - Cm(0.1), BOT_T, BOT_H)

# 시스템 구성 제목
section_title(slide, PAD, BOT_T, FLOW_W, "시스템 구성")

# 주요 기능 제목
section_title(slide, FEAT_L, BOT_T, FEAT_W, "주요 기능")

# ── 흐름도 (좌→우) ───────────────────────────────────────────────────────────
nodes = [
    ("👤 FA 담당자",           "SN 입력"),
    ("💬 Knox Messenger",       "메시지 전달"),
    ("⚙ FA 분석\n자동화 서버", "분석 요청 수신"),
    ("🗄 빅데이터\n포털",       "자동 조회"),
    ("📄 분석 결과\n생성",      "PDF / HTML"),
    ("💬 Knox Messenger",       "결과 전달"),
    ("👤 FA 담당자",            "결과 수신"),
]
N      = len(nodes)
ARR_W  = Cm(0.55)
NODE_W = (FLOW_W - PAD - ARR_W * (N - 1) - Cm(0.1)) / N
NODE_H = Cm(1.05)
NODE_T = BOT_T + Cm(0.7) + (BOT_H - Cm(0.7) - NODE_H) / 2

for i, (top, bot) in enumerate(nodes):
    nl = PAD + i * (NODE_W + ARR_W)
    flow_node(slide, nl, NODE_T, NODE_W, NODE_H, top, bot)
    if i < N - 1:
        arrow_r(slide, nl + NODE_W, NODE_T + NODE_H / 2 - Cm(0.175), ARR_W, Cm(0.35))

# ── 주요 기능 목록 ─────────────────────────────────────────────────────────
fy = BOT_T + Cm(0.7)
feats = [
    ("SN 기반 자동 분석",     "Knox Messenger · Adaptive Card · 다중 SN 지원"),
    ("빅데이터 자동 조회",    "포털 자동화 (Playwright) · 병렬 처리"),
    ("분석 리포트 자동 전송", "PDF / HTML 생성 → Knox Messenger 전달"),
    ("24/7 무인 대응",        "주말·야간 자동 처리 · 오류 알림"),
]
item_h = (BOT_H - Cm(0.75)) / len(feats)
for i, (title, desc) in enumerate(feats):
    rect(slide, FEAT_L + Cm(0.15), fy + Cm(0.1), Cm(0.1), Cm(0.42), fill=NAVY)
    txt(slide, title, FEAT_L + Cm(0.4), fy + Cm(0.05),
        FEAT_W - Cm(0.4), Cm(0.42), sz=9, bold=True, color=DGRAY)
    txt(slide, desc, FEAT_L + Cm(0.4), fy + Cm(0.46),
        FEAT_W - Cm(0.4), Cm(0.38), sz=8, color=MGRAY, italic=True)
    fy += item_h
    if i < len(feats) - 1:
        divider_h(slide, FEAT_L + Cm(0.15), fy - Cm(0.05), FEAT_W - Cm(0.15))

# ── 푸터 ──────────────────────────────────────────────────────────────────────
rect(slide, 0, H - Cm(0.52), W, Cm(0.52), fill=NAVY)
txt(slide, "Samsung Electronics Service  ·  Field Analysis Chatbot Automation  ·  2025",
    Cm(0.6), H - Cm(0.48), W * 0.75, Cm(0.38), sz=7.5, color=RGBColor(0xA0, 0xB2, 0xCC))
txt(slide, "Confidential", W - Cm(2.2), H - Cm(0.48), Cm(1.9), Cm(0.38),
    sz=8, bold=True, color=WHITE, align=PP_ALIGN.RIGHT)

# ════════════════════════════════════════════════════════════════════════════
out = "/home/user/FA-service/FA_챗봇_보고서.pptx"
prs.save(out)
print(f"저장 완료: {out}")
