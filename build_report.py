"""
수행평가 보고서 PDF 빌더
================================================
data.json, routes.json 의 실제 결과를 반영하여
report.pdf 를 자동 생성합니다.

스크린샷이 있으면 screenshots/ 폴더에 두세요:
  - screenshots/main.png    → 메인 화면 (좌측 카드 + 우측 지도)
  - screenshots/map.png     → 위성 지도 + 등록된 코스
  - screenshots/hourly.png  → 시간대별 산책지수 그리드
  - screenshots/app.png     → 파이썬 GUI (app.py) 화면

실행:  py build_report.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ──────────────────────────────────────────────────────────────
# 한글 폰트 등록 (윈도우 기본 '맑은 고딕')
# ──────────────────────────────────────────────────────────────
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Malgun", str(FONT_DIR / "malgun.ttf")))
pdfmetrics.registerFont(TTFont("MalgunBd", str(FONT_DIR / "malgunbd.ttf")))


# ──────────────────────────────────────────────────────────────
# 스타일
# ──────────────────────────────────────────────────────────────
PRIMARY = HexColor("#3182f6")
SUB = HexColor("#6b7684")
LINE = HexColor("#e9ecef")
BG_SOFT = HexColor("#f4f6f9")
GOOD = HexColor("#1ec979")

styles = getSampleStyleSheet()

H_TITLE = ParagraphStyle(
    "H_Title", parent=styles["Title"],
    fontName="MalgunBd", fontSize=22, leading=28,
    textColor=black, spaceAfter=8, alignment=1,
)
H_SUBTITLE = ParagraphStyle(
    "H_Sub", parent=styles["Normal"],
    fontName="Malgun", fontSize=12, leading=18,
    textColor=SUB, alignment=1, spaceAfter=24,
)
H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontName="MalgunBd", fontSize=15, leading=22,
    textColor=PRIMARY, spaceBefore=14, spaceAfter=8,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="MalgunBd", fontSize=12, leading=18,
    textColor=black, spaceBefore=10, spaceAfter=4,
)
BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"],
    fontName="Malgun", fontSize=10.5, leading=17,
    textColor=black, spaceAfter=6,
)
SMALL = ParagraphStyle(
    "Small", parent=styles["BodyText"],
    fontName="Malgun", fontSize=9, leading=14,
    textColor=SUB,
)
CODE = ParagraphStyle(
    "Code", parent=styles["Code"],
    fontName="Malgun", fontSize=9.5, leading=14,
    leftIndent=8, textColor=black,
    backColor=BG_SOFT, borderPadding=6, borderRadius=4,
)


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def build_table(data: list[list[str]], col_widths: list[float] | None = None,
                header: bool = True) -> Table:
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Malgun"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
    ]
    if header:
        style += [
            ("FONTNAME", (0, 0), (-1, 0), "MalgunBd"),
            ("BACKGROUND", (0, 0), (-1, 0), BG_SOFT),
            ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
        ]
    t.setStyle(TableStyle(style))
    return t


# ──────────────────────────────────────────────────────────────
# data.json / routes.json 로드
# ──────────────────────────────────────────────────────────────
def load_artifacts(base_dir: Path) -> tuple[dict, dict]:
    data = json.loads((base_dir / "data.json").read_text(encoding="utf-8"))
    routes = json.loads((base_dir / "routes.json").read_text(encoding="utf-8"))
    return data, routes


# ──────────────────────────────────────────────────────────────
# 본문 구성
# ──────────────────────────────────────────────────────────────
def build_story(base_dir: Path, data: dict, routes: dict) -> list:
    story: list = []
    school = routes.get("school", {})
    schedule = routes.get("schedule", [])
    user_routes = [r for r in routes.get("routes", []) if not r.get("_placeholder")]

    # ── 표지 ──
    story.append(Spacer(1, 60))
    story.append(P("정보 교과 5월 프로젝트 수행평가 보고서", H_TITLE))
    story.append(P(
        "공공데이터 API를 활용한<br/>"
        "‘기숙사 학생을 위한 캠퍼스 산책지수’ 웹앱 개발",
        H_SUBTITLE,
    ))
    cover = build_table([
        ["학교", school.get("name", "전북과학고등학교")],
        ["학년·반·번호", "1학년 3반 16번"],
        ["이름", "조윤호"],
        ["제출일", datetime.now().strftime("%Y년 %m월 %d일")],
    ], col_widths=[40 * mm, 110 * mm], header=False)
    story.append(cover)
    story.append(PageBreak())

    # ── 1. 프로젝트 개요 ──
    story.append(P("1. 프로젝트 개요", H1))
    story.append(P(
        "본 프로젝트는 공공데이터포털에서 제공하는 두 가지 OpenAPI를 결합하여 "
        "<b>전북과학고등학교 캠퍼스 내에서의 시간대별 산책 적합도 지수</b>를 산출하고, "
        "이를 정적 웹 페이지와 파이썬 데스크톱 GUI로 동시에 시각화한 결과물입니다. "
        "기상청 단기예보 데이터와 한국환경공단 에어코리아의 대기오염 정보를 함께 활용하여 "
        "단일 데이터로는 알 수 없는 통합 정보를 학교 일과표와 매칭하여 제공하도록 "
        "설계하였습니다."
    ))
    overview_table = build_table([
        ["항목", "내용"],
        ["주제", "공공데이터 API를 활용한 캠퍼스 산책지수 웹앱"],
        ["사용 데이터", "기상청 단기예보, 한국환경공단 에어코리아 대기오염정보"],
        ["기술 스택", "Python 3, HTML, CSS, JavaScript, Leaflet, tkinter"],
        ["배포 방식", "GitHub 저장소 공유 (정적 웹 호스팅 가능)"],
        ["대상 사용자", "전북과학고등학교 기숙사 학생"],
    ], col_widths=[40 * mm, 110 * mm])
    story.append(overview_table)

    # ── 2. 주제 선정 배경 ──
    story.append(P("2. 주제 선정 배경", H1))
    story.append(P(
        "전북과학고등학교는 기숙사 생활을 기반으로 운영되는 학교이므로, 학생들의 산책 활동 "
        "범위는 <b>학교 캠퍼스 내부</b>로 한정됩니다. 학생들이 산책 약속을 잡거나 잠시 "
        "바람을 쐬려 할 때, 보통은 날씨 앱과 미세먼지 앱을 따로 확인한 뒤 머릿속에서 두 "
        "정보를 결합하여 판단하게 됩니다. 이러한 과정은 번거로울 뿐 아니라, 어떤 변수에 "
        "더 큰 가중치를 두어야 하는지 사용자마다 기준이 달라 일관된 판단이 어렵다는 한계가 "
        "있습니다."
    ))
    story.append(P(
        "또한 기숙사 학생들에게 실제로 산책이 가능한 시간은 한정되어 있습니다. 등교 전 "
        "아침 시간, 점심식사 후 짧은 휴식, 야자 중 쉬는 시간, 야자 종료 후 취침 전 등 "
        "<b>특정한 시간대에만 외출이 가능</b>하며, 이 시간대에 산책에 적합한 날씨인지를 "
        "판단하는 일은 단순 날씨 조회보다 한 단계 더 복잡합니다."
    ))
    story.append(P(
        "이에 본 프로젝트에서는 두 가지 공공데이터 API를 결합하여 산책지수를 계산하고, "
        "이를 학교의 실제 일과표(아침·점심·야자 쉬는 시간·야자 후)와 매칭하여 "
        "<b>‘오늘 어느 일과 슬롯에 나가는 것이 가장 좋은가’</b>를 객관적인 점수로 보여주는 "
        "웹앱과 데스크톱 GUI를 개발하였습니다."
    ))

    # ── 3. 차별점 ──
    story.append(P("3. 본 프로젝트의 차별점", H1))
    diff_table = build_table([
        ["구분", "차별 요소"],
        ["데이터 결합", "두 개 API를 결합하여 산책 적합도라는 통합 지수를 산출"],
        ["일과표 매칭", "학교 실제 일과(아침/점심/야자 쉬는 시간/야자 후) 4개 슬롯에 점수 자동 매칭"],
        ["좌표 처리", "위경도 → 기상청 LCC 격자 변환 공식을 직접 구현하여 학교 정확 좌표 사용"],
        ["지도 시각화", "Esri 위성 사진 위에 캠퍼스 산책 코스를 폴리라인으로 표시"],
        ["사용자 그리기", "방문자가 위성 사진 위에 직접 산책 경로를 그려 저장 가능 (관리자/개인 분리)"],
        ["UX 설계", "토스(Toss)풍 카드 레이아웃, 친구 같은 추천 메시지, 데스크톱 사이드+메인 2컬럼"],
        ["듀얼 화면", "정적 웹페이지와 동일한 정보를 파이썬 tkinter GUI(app.py)로도 제공"],
        ["보안 설계", ".env 파일 분리 및 .gitignore 처리로 인증키 노출을 원천 차단"],
    ], col_widths=[35 * mm, 115 * mm])
    story.append(diff_table)

    # ── 4. 시스템 구조 ──
    story.append(P("4. 시스템 구조", H1))
    story.append(P(
        "전체 시스템은 데이터 수집 단계와 표시 단계를 분리한 구조로 설계하였습니다. "
        "Python 스크립트(<b>fetch_data.py</b>)가 두 OpenAPI를 호출하여 산책지수를 계산한 뒤 "
        "정적 JSON 파일(<b>data.json</b>)로 저장하면, 두 가지 표시 채널이 이를 비동기로 "
        "읽어 화면에 렌더링합니다."
    ))
    story.append(P(
        "  · <b>웹 채널</b> — index.html / style.css / script.js 가 data.json 과 routes.json 을 "
        "읽어 토스 스타일 카드 + Leaflet 위성 지도로 표시<br/>"
        "  · <b>데스크톱 채널</b> — app.py 가 동일한 데이터를 tkinter 창으로 표시 "
        "(웹 페이지와 같은 정보·같은 레이아웃)"
    ))
    story.append(P(
        "이러한 구조는 인증키를 클라이언트 측에 노출하지 않으면서도 GitHub Pages와 같은 "
        "정적 호스팅 환경에서 배포가 가능하다는 장점을 가집니다."
    ))
    story.append(P(
        "[공공데이터 OpenAPI 2종]<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;↓ HTTP<br/>"
        "fetch_data.py (Python)  →  data.json + routes.json<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
        "  ① index.html / script.js  →  Leaflet 지도 + 카드 (브라우저)<br/>"
        "  ② app.py  →  tkinter 카드 그리드 (데스크톱 창)",
        ParagraphStyle("flow", parent=BODY, fontName="Courier", fontSize=9.5,
                       leading=14, backColor=BG_SOFT, borderPadding=8)
    ))

    # ── 5. 산책지수 산출 알고리즘 ──
    story.append(P("5. 산책지수 산출 알고리즘", H1))
    story.append(P(
        "산책지수는 <b>기상 점수(만점 50)</b>와 <b>대기 점수(만점 50)</b>의 합으로 0점부터 "
        "100점까지의 값을 가집니다. 점수가 높을수록 해당 시간대가 산책에 적합함을 의미합니다."
    ))
    story.append(P("5-1. 기상 점수 산정", H2))
    weather_table = build_table([
        ["변수", "기준", "감점"],
        ["기온(TMP)", "15℃ 이상 22℃ 이하", "0"],
        ["기온", "10–14℃ 또는 23–26℃", "-5"],
        ["기온", "5–9℃ 또는 27–30℃", "-12"],
        ["기온", "그 외 범위", "-22"],
        ["강수형태(PTY)", "비, 비/눈, 눈, 소나기", "-30"],
        ["강수확률(POP)", "60% 이상", "-18"],
        ["강수확률", "30% 이상 59% 이하", "-8"],
        ["풍속(WSD)", "9 m/s 이상", "-12"],
        ["풍속", "5–8 m/s", "-5"],
        ["하늘상태(SKY)", "흐림", "-3"],
    ], col_widths=[40 * mm, 75 * mm, 35 * mm])
    story.append(weather_table)

    story.append(P("5-2. 대기 점수 산정", H2))
    story.append(P(
        "환경부의 4단계 미세먼지 등급을 기준으로, PM10과 PM2.5 두 항목 중 "
        "<b>더 나쁜 등급</b>을 채택하여 점수를 부여합니다."
    ))
    air_table = build_table([
        ["등급", "PM10 (㎍/㎥)", "PM2.5 (㎍/㎥)", "점수"],
        ["좋음", "0–30", "0–15", "50"],
        ["보통", "31–80", "16–35", "38"],
        ["나쁨", "81–150", "36–75", "18"],
        ["매우나쁨", "151 이상", "76 이상", "5"],
    ], col_widths=[28 * mm, 42 * mm, 42 * mm, 38 * mm])
    story.append(air_table)

    # ── 6. 학교 일과 슬롯 매칭 ──
    story.append(P("6. 학교 일과 슬롯 매칭", H1))
    story.append(P(
        "기숙사 학생의 실제 산책 가능 시간을 반영하여 다음 4개 시간대를 일과 슬롯으로 "
        "지정하였습니다. 각 슬롯에는 해당 시간대 평균 산책지수와 슬롯 내 가장 높은 점수의 "
        "시각이 자동으로 매칭되며, 4개 슬롯 중 평균 점수가 가장 높은 슬롯에는 ‘오늘 추천’ "
        "배지가 표시됩니다."
    ))
    schedule_rows = [["슬롯", "시간", "용도"]]
    for s in schedule:
        schedule_rows.append([
            f"{s.get('icon', '')} {s.get('label', '')}",
            f"{s.get('start', '')}~{s.get('end', '')}",
            s.get("subtitle", ""),
        ])
    if len(schedule_rows) == 1:
        schedule_rows.append(["—", "—", "routes.json에 등록된 슬롯 없음"])
    story.append(build_table(schedule_rows, col_widths=[40 * mm, 32 * mm, 78 * mm]))

    # ── 7. 캠퍼스 산책 코스 ──
    story.append(P("7. 캠퍼스 산책 코스 (사용자 등록)", H1))
    story.append(P(
        "본 시스템은 학생이 위성 지도(Esri World Imagery) 위에 직접 점을 찍어 "
        "<b>캠퍼스 내 산책 경로</b>를 등록할 수 있도록 설계되었습니다. 등록된 코스는 "
        "산책지수의 추천 임계점수와 결합되어, 점수가 높은 날에는 더 긴 코스가, 낮은 날에는 "
        "짧은 코스만 ‘추천’ 배지로 강조됩니다. 또한 일반 방문자(친구)는 자기 개인 코스를 "
        "별도로 그려 브라우저에 저장(localStorage)할 수 있어, 관리자(코스 등록자)와 "
        "방문자의 데이터가 분리됩니다."
    ))
    if user_routes:
        course_rows = [["코스명", "거리", "예상 시간", "추천 임계 점수", "설명"]]
        for r in user_routes:
            course_rows.append([
                r.get("name", "-"),
                f"{r.get('distance_km', '?')} km",
                f"{r.get('duration_min', '?')} 분",
                str(r.get("min_score", "-")),
                r.get("subtitle", ""),
            ])
        story.append(build_table(
            course_rows,
            col_widths=[34 * mm, 22 * mm, 22 * mm, 28 * mm, 44 * mm],
        ))
    else:
        story.append(P("(아직 등록된 코스가 없습니다.)", SMALL))

    # ── 8. 핵심 코드 설명 ──
    story.append(PageBreak())
    story.append(P("8. 핵심 코드 설명", H1))
    story.append(P("8-1. 위경도 → 기상청 격자 좌표 변환", H2))
    story.append(P(
        f"기상청 단기예보 API는 동네예보 격자 좌표(nx, ny)를 입력으로 요구합니다. 이를 "
        f"위해 위경도를 격자 좌표로 변환하는 LCC(Lambert Conformal Conic) 투영 공식을 "
        f"직접 구현하였습니다. 학교 정확 좌표 "
        f"(위도 {school.get('lat', '-')}°, 경도 {school.get('lon', '-')}°)를 변환한 결과 "
        f"<b>nx=61, ny=93</b> 격자가 도출되었으며, 함수의 정확성은 서울(60, 127), "
        f"부산(98, 76), 인천(55, 124) 등 기상청 공개 격자값과 일치하는지 검증하여 확인하였습니다."
    ))
    story.append(P(
        "def latlon_to_grid(lat, lon):<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;RE, GRID = 6371.00877, 5.0<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;SLAT1, SLAT2 = 30.0, 60.0<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;OLON, OLAT = 126.0, 38.0<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;XO, YO = 43, 136<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;# (LCC 공식 적용 후 nx, ny 정수 반환)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;return nx, ny",
        CODE,
    ))

    story.append(P("8-2. 두 API 호출과 측정소 매칭", H2))
    story.append(P(
        "기상청 API는 발표시각(02, 05, 08, 11, 14, 17, 20, 23시) 중 가장 최근 시각을 "
        "선택하여 호출하고, 응답에서 카테고리(TMP, POP, WSD, SKY, PTY)를 시간대별로 "
        "추출합니다. 에어코리아 API는 학교가 위치한 행정동(전북 익산시 금마면)과 "
        "동일한 도시대기 측정소인 <b>금마면 측정소</b>를 우선 조회하며, 측정값을 받지 못할 "
        "경우 시도(전북) 단위 조회로 자동 폴백하도록 처리하였습니다."
    ))

    story.append(P("8-3. 인증키 보안 처리", H2))
    story.append(P(
        "공공데이터포털에서 발급받은 일반 인증키는 <b>.env</b> 파일에 분리하여 저장하고, "
        "<b>.gitignore</b> 설정을 통해 GitHub 저장소에 업로드되지 않도록 차단하였습니다. "
        "또한 학생 본인의 식별 정보가 포함된 본 보고서 파일 또한 동일한 방식으로 저장소에서 "
        "제외하여 개인정보 노출을 원천적으로 방지하였습니다."
    ))

    # ── 9. 보안 / 개인정보 ──
    story.append(P("9. 개인정보 보호 설계", H1))
    privacy_table = build_table([
        ["고려한 위협", "본 프로젝트의 대응"],
        ["API 인증키 GitHub 노출", ".env 파일 분리 + .gitignore 제외"],
        ["사용자 위치정보 추적", "위치 권한 요청 없음, 학교 좌표 고정값 사용"],
        ["사용자 식별 정보 수집", "로그인·입력 폼 미운영, 접속자 데이터 미수집"],
        ["Git 커밋 시 이메일 노출", "GitHub noreply 이메일 사용 권장"],
        ["보고서 내 식별 정보 노출", "report.pdf / report.md 파일을 .gitignore 처리"],
    ], col_widths=[55 * mm, 95 * mm])
    story.append(privacy_table)

    # ── 10. 결과 화면 (스크린샷) ──
    story.append(PageBreak())
    story.append(P("10. 결과 화면", H1))
    shots_dir = base_dir / "screenshots"
    shots = [
        ("main.png",   "[그림 1] 메인 화면 (좌측: 황금시간/슬롯/미세먼지 카드, 우측: 위성 지도)"),
        ("map.png",    "[그림 2] 위성 사진 + 등록된 캠퍼스 산책 코스 폴리라인"),
        ("hourly.png", "[그림 3] 시간대별 산책지수 그리드 (24시간)"),
        ("app.png",    "[그림 4] 파이썬 데스크톱 GUI (app.py) 화면"),
    ]
    inserted = False
    for fname, caption in shots:
        path = shots_dir / fname
        if path.exists():
            try:
                img = Image(str(path), width=150 * mm, height=95 * mm,
                            kind="proportional")
                story.append(img)
                story.append(P(caption, SMALL))
                story.append(Spacer(1, 8))
                inserted = True
            except Exception as e:
                story.append(P(f"이미지 로드 실패: {fname} ({e})", SMALL))

    if not inserted:
        story.append(P(
            "※ 본 보고서를 출력하기 전, 아래 4개 화면을 캡처하여 "
            "<b>screenshots/</b> 폴더에 저장한 후 build_report.py 를 다시 실행하시면 "
            "자동으로 이 위치에 삽입됩니다.",
            BODY,
        ))
        story.append(P(
            "&nbsp;&nbsp;• screenshots/main.png &nbsp;&nbsp;— 메인 화면 (전체)<br/>"
            "&nbsp;&nbsp;• screenshots/map.png &nbsp;&nbsp;&nbsp;— 위성 지도 + 코스<br/>"
            "&nbsp;&nbsp;• screenshots/hourly.png — 시간대별 그리드<br/>"
            "&nbsp;&nbsp;• screenshots/app.png &nbsp;&nbsp;&nbsp;— 파이썬 GUI",
            BODY,
        ))

    # ── 11. 발전 방향 ──
    story.append(P("11. 발전 방향", H1))
    story.append(P(
        "본 프로젝트는 두 종류의 공공데이터를 결합하는 데에 집중하였으나, 향후에는 다음과 "
        "같은 방향으로 기능을 확장할 수 있을 것으로 판단됩니다."
    ))
    story.append(P(
        "&nbsp;&nbsp;• <b>지도 API 연계</b> — 카카오맵 또는 네이버 지도 API와 결합하여 "
        "학교 주변의 산책 코스를 더욱 정밀하게 시각화<br/>"
        "&nbsp;&nbsp;• <b>주기적 자동 갱신</b> — GitHub Actions의 cron 기능을 사용하여 "
        "fetch_data.py 를 매시 자동 실행하도록 구성<br/>"
        "&nbsp;&nbsp;• <b>알림 기능</b> — Progressive Web App(PWA) 기술을 적용하여 "
        "‘지금이 산책 황금시간’과 같은 푸시 알림을 제공<br/>"
        "&nbsp;&nbsp;• <b>데이터 확장</b> — 기상청 자외선 지수, 환경부 꽃가루 지수 등을 "
        "추가하여 봄철 알레르기 학생을 위한 정보까지 통합<br/>"
        "&nbsp;&nbsp;• <b>다중 학교 확장</b> — 좌표와 일과표를 데이터 파일로 분리하였으므로, "
        "타 학교에도 동일 시스템을 손쉽게 적용 가능"
    ))

    # ── 12. 느낀 점 ──
    story.append(P("12. 프로젝트를 마치며", H1))
    story.append(P(
        "본 프로젝트를 진행하며, 공공데이터를 단순히 가져와 보여주는 단계를 넘어 "
        "<b>서로 다른 출처의 데이터를 결합하여 새로운 가치를 만들어 내는 과정</b>의 "
        "중요성을 체감할 수 있었습니다. 특히 기상청 LCC 격자 좌표 변환 공식을 직접 구현해 "
        "보며, 데이터가 격자로 표준화되는 방식과 그 표준이 사용자에게 도달하기까지의 여정을 "
        "깊이 이해하게 되었습니다."
    ))
    story.append(P(
        "또한 처음에 학교 위치를 잘못 추정하여 잘못된 격자(60, 95)를 사용하다가 위키백과에서 "
        "정확한 주소(전북 익산시 금마면 용순신기길 48-69)를 확인하여 올바른 격자(61, 93)와 "
        "측정소(금마면)로 수정한 경험은, <b>데이터 출처 검증의 중요성</b>을 직접 체감하게 "
        "해주었습니다."
    ))
    story.append(P(
        "기숙사 학생의 일과표를 반영하여 산책지수를 매칭하는 설계 또한, 단순한 데이터 시각화를 "
        "넘어 <b>실제 사용자의 맥락에 맞춘 정보 제공</b>의 가치를 깨닫게 한 과정이었습니다. "
        "본 결과물이 동료 학생들에게 작은 편의를 제공할 수 있기를 기대합니다."
    ))

    # ── 13. 데이터 출처 ──
    story.append(P("13. 데이터 출처", H1))
    story.append(P(
        "본 프로그램에서 사용한 공공데이터 및 외부 자원의 출처는 다음과 같습니다."
    ))
    story.append(P(
        "&nbsp;&nbsp;• <b>기상청 _ 단기예보 조회서비스</b> "
        "(공공데이터포털, 데이터셋 ID 15084084)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;https://www.data.go.kr/data/15084084/openapi.do<br/>"
        "&nbsp;&nbsp;• <b>한국환경공단 _ 에어코리아 _ 대기오염정보</b> "
        "(공공데이터포털, 데이터셋 ID 15073861)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;https://www.data.go.kr/data/15073861/openapi.do<br/>"
        "&nbsp;&nbsp;• 위성 영상: Esri, Maxar, Earthstar Geographics, GIS User Community<br/>"
        "&nbsp;&nbsp;• 일반 지도: OpenStreetMap contributors<br/>"
        "&nbsp;&nbsp;• 격자 좌표 변환 공식: 기상청 동네예보 LCC DFS 변환 공식<br/>"
        "&nbsp;&nbsp;• 학교 좌표 출처: 위키백과 ‘전북과학고등학교’ 항목"
    ))

    return story


# ──────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────
def main() -> int:
    base_dir = Path(__file__).resolve().parent
    data, routes = load_artifacts(base_dir)
    out = base_dir / "report.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title="정보 교과 5월 프로젝트 수행평가 보고서",
        author="조윤호",
    )
    story = build_story(base_dir, data, routes)
    doc.build(story)
    print(f"[OK] {out.name} 생성 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
