"""
수행평가 보고서 PDF 빌더
================================================
data.json, routes.json 의 실제 결과를 반영하여 report.pdf 를 생성합니다.

screenshots/ 폴더에 PNG 가 있으면 결과 화면 섹션에 자동 삽입됩니다.
  - main.png   : 웹 페이지 전체
  - map.png    : 위성 지도 + 코스
  - hourly.png : 시간대별 그리드
  - app.png    : 파이썬 GUI

실행:  py build_report.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

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


# 한글 폰트 등록 (윈도우 기본 '맑은 고딕')
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Malgun", str(FONT_DIR / "malgun.ttf")))
pdfmetrics.registerFont(TTFont("MalgunBd", str(FONT_DIR / "malgunbd.ttf")))


# 색상
PRIMARY = HexColor("#3182f6")
SUB = HexColor("#6b7684")
LINE = HexColor("#e9ecef")
BG_SOFT = HexColor("#f4f6f9")


# 스타일
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


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def build_table(data, col_widths=None, header=True) -> Table:
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


def load_artifacts(base_dir: Path):
    data = json.loads((base_dir / "data.json").read_text(encoding="utf-8"))
    routes = json.loads((base_dir / "routes.json").read_text(encoding="utf-8"))
    return data, routes


# ──────────────────────────────────────────────────────────────
# 본문
# ──────────────────────────────────────────────────────────────
def build_story(base_dir: Path, data: dict, routes: dict) -> list:
    story: list = []
    school = routes.get("school", {})
    schedule = routes.get("schedule", [])
    user_routes = [r for r in routes.get("routes", []) if not r.get("_placeholder")]

    # 표지
    story.append(Spacer(1, 60))
    story.append(P("정보 교과 5월 프로젝트 수행평가 보고서", H_TITLE))
    story.append(P(
        "공공데이터 API로 만든<br/>"
        "기숙사 학생용 캠퍼스 산책지수 웹앱",
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

    # 1. 개요
    story.append(P("1. 프로젝트 개요", H1))
    story.append(P(
        "공공데이터포털에 있는 기상청 단기예보와 한국환경공단 에어코리아 두 API를 같이 "
        "써서, 우리 학교에서 산책하기 좋은 시간대를 점수로 알려주는 웹앱을 만들었습니다. "
        "같은 내용을 보여주는 파이썬 데스크톱 화면도 함께 만들었습니다."
    ))
    story.append(build_table([
        ["항목", "내용"],
        ["주제", "공공데이터 API로 만든 캠퍼스 산책지수"],
        ["사용한 데이터", "기상청 단기예보, 한국환경공단 에어코리아 대기오염정보"],
        ["사용 언어", "Python, HTML, CSS, JavaScript"],
        ["배포 방식", "GitHub Pages (정적 호스팅)"],
        ["대상", "전북과학고등학교 기숙사 학생"],
    ], col_widths=[40 * mm, 110 * mm]))

    # 2. 주제 선정 이유
    story.append(P("2. 주제를 정한 이유", H1))
    story.append(P(
        "전북과학고등학교는 기숙사 학교라서 학생들이 산책할 수 있는 공간이 학교 안으로 "
        "한정됩니다. 산책을 가려고 할 때 보통은 날씨 앱과 미세먼지 앱을 따로 켜서 "
        "확인하는데, 두 가지를 같이 보고 ‘지금 나가도 되는지’ 판단하는 게 은근히 "
        "번거롭습니다."
    ))
    story.append(P(
        "또 기숙사 일과 때문에 실제로 산책이 가능한 시간은 정해져 있습니다. 아침, 점심, "
        "야자 쉬는 시간, 야자 끝난 후 정도가 거의 전부입니다. 그래서 ‘오늘 어느 시간이 "
        "가장 좋은지’를 한 화면에서 바로 알 수 있으면 친구들과 산책 약속을 잡을 때 "
        "편할 것 같다고 생각해서 이 주제를 골랐습니다."
    ))

    # 3. 특징
    story.append(P("3. 이 프로그램의 특징", H1))
    story.append(build_table([
        ["구분", "특징"],
        ["데이터 결합", "두 개 API 결과를 합쳐서 0~100점 산책지수를 계산"],
        ["일과표 매칭", "아침/점심/야자 쉬는 시간/야자 후 4개 슬롯에 점수 자동 매칭"],
        ["좌표 변환", "위경도를 기상청 격자 좌표로 바꾸는 공식을 직접 구현"],
        ["지도", "Esri 위성 사진 위에 캠퍼스 산책 코스를 그려 표시"],
        ["사용자 그리기", "방문자가 위성 사진 위에 직접 점을 찍어 코스를 만들 수 있음"],
        ["듀얼 화면", "웹 페이지와 파이썬 데스크톱 화면 두 가지로 같은 정보 제공"],
        ["보안", "API 키와 보고서는 .gitignore 처리해서 GitHub 에 안 올라가게"],
    ], col_widths=[35 * mm, 115 * mm]))

    # 4. 시스템 구조
    story.append(P("4. 시스템 구조", H1))
    story.append(P(
        "데이터를 받아오는 부분과 보여주는 부분을 분리했습니다. fetch_data.py 가 두 "
        "API를 호출해서 결과를 data.json 파일로 저장하고, 웹페이지(index.html)와 "
        "파이썬 GUI(app.py)는 각각 그 파일을 읽어서 화면에 표시합니다."
    ))
    story.append(P(
        "이렇게 분리한 이유는 두 가지입니다. 첫째, 인증키가 사용자 브라우저에 노출되지 "
        "않습니다. 둘째, GitHub Pages 같은 정적 호스팅에서도 잘 작동합니다. "
        "키는 본인 컴퓨터의 .env 파일에만 있고, GitHub 에는 결과 데이터(data.json)만 "
        "올라갑니다."
    ))
    story.append(P(
        "추가로 GitHub Actions 의 cron 기능을 써서 매시간 자동으로 fetch_data.py 가 "
        "실행되도록 설정했습니다. 사용자가 따로 손대지 않아도 페이지가 항상 최신 "
        "데이터로 갱신됩니다."
    ))

    # 5. 산책지수
    story.append(P("5. 산책지수 계산 방식", H1))
    story.append(P(
        "산책지수는 <b>기상 점수(50점) + 대기 점수(50점)</b> 으로 0~100점 사이의 값을 "
        "갖습니다. 점수가 높을수록 산책하기 좋다는 뜻입니다."
    ))
    story.append(P("5-1. 기상 점수", H2))
    story.append(build_table([
        ["변수", "기준", "감점"],
        ["기온", "15~22℃", "0"],
        ["기온", "10~14℃ 또는 23~26℃", "-5"],
        ["기온", "5~9℃ 또는 27~30℃", "-12"],
        ["기온", "그 외", "-22"],
        ["강수형태", "비, 비/눈, 눈, 소나기", "-30"],
        ["강수확률", "60% 이상", "-18"],
        ["강수확률", "30~59%", "-8"],
        ["풍속", "9 m/s 이상", "-12"],
        ["풍속", "5~8 m/s", "-5"],
        ["하늘", "흐림", "-3"],
    ], col_widths=[40 * mm, 75 * mm, 35 * mm]))

    story.append(P("5-2. 대기 점수", H2))
    story.append(P(
        "환경부의 4단계 미세먼지 등급을 기준으로 PM10과 PM2.5 중 더 나쁜 등급을 "
        "골라서 점수를 매깁니다."
    ))
    story.append(build_table([
        ["등급", "PM10 (㎍/㎥)", "PM2.5 (㎍/㎥)", "점수"],
        ["좋음", "0~30", "0~15", "50"],
        ["보통", "31~80", "16~35", "38"],
        ["나쁨", "81~150", "36~75", "18"],
        ["매우나쁨", "151 이상", "76 이상", "5"],
    ], col_widths=[28 * mm, 42 * mm, 42 * mm, 38 * mm]))

    # 6. 일과 슬롯
    story.append(P("6. 학교 일과에 맞춘 슬롯", H1))
    story.append(P(
        "기숙사 학생이 실제로 산책 갈 수 있는 시간 4개를 일과 슬롯으로 정했습니다. "
        "각 슬롯에는 그 시간대의 평균 점수와 그 안에서 가장 점수 높은 시각이 같이 "
        "표시되고, 4개 중 평균이 가장 높은 슬롯에는 ‘오늘 추천’ 표시가 자동으로 "
        "붙습니다."
    ))
    rows = [["슬롯", "시간", "용도"]]
    for s in schedule:
        rows.append([
            f"{s.get('icon', '')} {s.get('label', '')}",
            f"{s.get('start', '')}~{s.get('end', '')}",
            s.get("subtitle", ""),
        ])
    if len(rows) == 1:
        rows.append(["—", "—", "(슬롯 없음)"])
    story.append(build_table(rows, col_widths=[40 * mm, 32 * mm, 78 * mm]))

    # 7. 산책 코스
    story.append(P("7. 캠퍼스 산책 코스", H1))
    story.append(P(
        "위성 사진 위에 마우스로 점을 찍어서 산책 경로를 직접 그릴 수 있게 만들었습니다. "
        "그린 코스는 두 가지로 저장할 수 있습니다. 하나는 ‘기본 추천 코스’ 로 "
        "routes.json 에 등록하면 다른 친구들에게도 보이고, 다른 하나는 ‘내 코스’ 로 "
        "본인 브라우저에만 저장됩니다."
    ))
    story.append(P(
        "코스마다 ‘추천 최소 점수’ 를 설정해서, 산책지수가 그 점수 이상일 때만 "
        "추천으로 표시됩니다. 예를 들어 긴 코스는 90점 이상일 때만 추천하고, 짧은 "
        "코스는 80점이어도 추천하는 식입니다."
    ))
    if user_routes:
        course_rows = [["코스명", "거리", "예상 시간", "추천 최소 점수", "설명"]]
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

    # 8. 핵심 코드
    story.append(PageBreak())
    story.append(P("8. 핵심 부분 설명", H1))

    story.append(P("8-1. 위경도를 기상청 격자 좌표로 바꾸기", H2))
    story.append(P(
        "기상청 단기예보 API 는 위경도가 아니라 격자 좌표(nx, ny)를 입력으로 받습니다. "
        "그래서 위경도를 격자로 바꿔주는 공식(LCC 투영법)을 직접 파이썬으로 구현했습니다. "
        "학교 좌표를 변환하니 nx=61, ny=93 이 나왔습니다. 함수가 맞는지 확인하려고 "
        "서울, 부산, 인천 같이 이미 알려진 도시 좌표를 넣어 보았는데 기상청에서 "
        "공개한 값과 모두 일치했습니다."
    ))

    story.append(P("8-2. 측정소 고르기", H2))
    story.append(P(
        "에어코리아 미세먼지 데이터는 측정소 이름으로 가져옵니다. 익산시에는 측정소가 "
        "8개 있는데, 학교가 있는 행정동(금마면)에 측정소가 마침 있어서 그걸 골랐습니다. "
        "혹시 측정소 데이터가 안 들어오면 시도(전북) 단위로 자동 폴백하도록 처리했습니다."
    ))

    story.append(P("8-3. 인증키 보호", H2))
    story.append(P(
        "공공데이터포털에서 받은 인증키를 코드에 직접 적으면 GitHub 에 올릴 때 같이 "
        "올라가서 누구나 볼 수 있게 됩니다. 그래서 키를 .env 파일에 따로 빼고, "
        ".gitignore 로 GitHub 업로드에서 제외했습니다. 이름과 학번이 들어간 보고서 "
        "PDF 도 같은 방식으로 처리했습니다."
    ))

    # 9. 개인정보
    story.append(P("9. 개인정보 보호", H1))
    story.append(build_table([
        ["고려한 부분", "처리 방식"],
        ["API 인증키 노출", ".env 파일 분리 + .gitignore 제외"],
        ["사용자 위치 추적", "위치 권한 요청 안 함, 학교 좌표만 코드에 고정"],
        ["접속자 정보 수집", "로그인·입력 폼 자체가 없음"],
        ["GitHub 커밋 이메일", "GitHub noreply 이메일로 설정"],
        ["보고서 안 개인정보", "report.pdf 도 .gitignore 처리해서 GitHub 에 안 올라감"],
    ], col_widths=[55 * mm, 95 * mm]))

    # 10. 결과 화면
    story.append(PageBreak())
    story.append(P("10. 결과 화면", H1))
    shots_dir = base_dir / "screenshots"
    shots = [
        ("main.png",   "[그림 1] 웹 페이지 전체 화면"),
        ("map.png",    "[그림 2] 위성 사진 위에 표시한 캠퍼스 산책 코스"),
        ("hourly.png", "[그림 3] 시간대별 산책지수"),
        ("app.png",    "[그림 4] 파이썬 데스크톱 화면 (app.py)"),
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
        story.append(P("(스크린샷이 아직 캡처되지 않았습니다.)", SMALL))

    # 11. 발전 방향
    story.append(P("11. 더 발전시킬 수 있는 방향", H1))
    story.append(P(
        "&nbsp;&nbsp;• 카카오맵이나 네이버 지도 API 를 같이 써서 지도를 더 자세하게 보여주기<br/>"
        "&nbsp;&nbsp;• 자외선이나 꽃가루 같은 데이터를 추가해서 봄철 알레르기 학생에게도 도움 되게<br/>"
        "&nbsp;&nbsp;• PWA 로 만들어서 ‘지금이 산책 좋은 시간이에요’ 같은 알림 보내기<br/>"
        "&nbsp;&nbsp;• 좌표와 일과표를 데이터 파일로 분리해 뒀기 때문에 다른 학교에도 쉽게 적용 가능"
    ))

    # 12. 마치며
    story.append(P("12. 마치며", H1))
    story.append(P(
        "처음에는 그냥 미세먼지나 날씨 정보 하나만 보여 주는 사이트를 만들 생각이었는데, "
        "두 가지를 같이 봐야 진짜 산책 갈지 결정할 수 있다는 걸 깨닫고 데이터를 합치는 "
        "쪽으로 방향을 바꿨습니다. 두 종류의 공공데이터를 합쳐서 하나의 점수로 만들면서, "
        "데이터를 단순히 보여주는 것과 ‘판단을 도와주는 도구’ 로 만드는 것의 차이를 "
        "느낄 수 있었습니다."
    ))
    story.append(P(
        "기억에 남는 부분은 학교 위치를 처음에 잘못 잡았던 일입니다. 망성면이라고 잘못 "
        "기억하고 있었는데 실제로는 금마면이었고, 그래서 격자 좌표도 측정소도 다 다른 "
        "지역으로 잡혀 있었습니다. 위키백과에서 정확한 주소를 확인해서 다시 계산하니까 "
        "비로소 학교 바로 위 격자(nx=61, ny=93)와 학교 옆 측정소(금마면)로 맞춰졌습니다. "
        "데이터 출처를 한 번 더 확인하는 습관이 중요하다는 걸 직접 체감했습니다."
    ))
    story.append(P(
        "또 기숙사 일과에 맞춰 4개 시간대를 따로 보여 주는 슬롯을 만든 게 가장 마음에 "
        "듭니다. 단순히 24시간 점수만 늘어놓는 것보다 ‘점심시간에 나갈지 야자 후에 "
        "나갈지’ 같은 실제 결정에 바로 도움이 되기 때문입니다. 공공데이터 자체는 누구나 "
        "받을 수 있지만, 그걸 우리 학교 상황에 맞게 가공하는 부분에서 차이가 생긴다는 "
        "걸 알게 됐습니다."
    ))

    # 13. 출처
    story.append(P("13. 데이터 출처", H1))
    story.append(P(
        "이 프로그램이 사용한 공공데이터와 외부 자원의 출처는 다음과 같습니다."
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
