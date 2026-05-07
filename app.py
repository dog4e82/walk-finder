"""
캠퍼스 산책지수 - 데스크톱 GUI
================================================
index.html 페이지와 같은 정보를 tkinter 윈도우로 보여주는
파이썬 화면입니다 (보고서가 아닌 '화면용' 파일).

화면 구성 (HTML 페이지와 동일):
  ┌──────────────────────────────────────────┐
  │ 헤더 · 학교칩 · 타이틀                   │
  ├───────────────┬──────────────────────────┤
  │ 좌측          │ 우측                     │
  │ - 황금시간    │ - 추천 산책 코스 목록    │
  │ - 산책 슬롯   │                          │
  │ - 미세먼지    │                          │
  ├───────────────┴──────────────────────────┤
  │ 하단 · 시간대별 점수 그리드              │
  ├──────────────────────────────────────────┤
  │ 푸터 · 데이터 출처                       │
  └──────────────────────────────────────────┘

실행:  py app.py
요구사항: data.json, routes.json (먼저 fetch_data.py 실행 필요)
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any


# ──────────────────────────────────────────────────────────────
# 토스 스타일 색상 팔레트 (style.css 와 동일)
# ──────────────────────────────────────────────────────────────
BG          = "#f4f6f9"
CARD        = "#ffffff"
TEXT        = "#191f28"
SUB         = "#6b7684"
LINE        = "#e9ecef"
PRIMARY     = "#3182f6"
PRIMARY_SOFT= "#e8f3ff"
GOOD        = "#1ec979"
GOOD_SOFT   = "#e6faf1"
WARN        = "#ffb800"
WARN_SOFT   = "#fff5d6"
BAD         = "#ff5c5c"
BAD_SOFT    = "#ffe7e7"


def score_color(score: float) -> tuple[str, str]:
    """점수에 맞는 (전경색, 배경색)."""
    if score >= 80: return GOOD, GOOD_SOFT
    if score >= 60: return PRIMARY, PRIMARY_SOFT
    if score >= 40: return "#b07a00", WARN_SOFT
    return BAD, BAD_SOFT


def air_label_to_color(label: str) -> tuple[str, str]:
    return {
        "좋음":     (GOOD,    GOOD_SOFT),
        "보통":     (PRIMARY, PRIMARY_SOFT),
        "나쁨":     ("#b07a00", WARN_SOFT),
        "매우나쁨": (BAD,     BAD_SOFT),
    }.get(label, (SUB, BG))


def friend_message(score: float) -> str:
    if score >= 80: return "오늘 진짜 산책각이야. 친구 불러봐"
    if score >= 60: return "괜찮은 정도. 잠깐 바람 쐬기엔 OK"
    if score >= 40: return "굳이? 안 나가도 되는 날인 듯"
    return "오늘은 매점 ㄱㄱ. 산책은 패스하자"


# ──────────────────────────────────────────────────────────────
# 데이터 로딩
# ──────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} 파일이 없어요. 먼저 'py fetch_data.py' 를 실행해 주세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_hhmm(s: str) -> float:
    h, m = (int(x) for x in s.split(":"))
    return h + m / 60


def slot_match(hourly: list[dict], slot: dict) -> dict | None:
    """슬롯 시간대에 해당하는 hourly 데이터 평균/베스트."""
    start = parse_hhmm(slot["start"])
    end = parse_hhmm(slot["end"])
    floor_h = int(start)
    ceil_h = -(-int(end * 100) // 100)  # ceil
    now = datetime.now()
    matches = []
    for h in hourly:
        try:
            dt = datetime.fromisoformat(h["datetime"])
        except Exception:
            continue
        if dt < now: continue
        if floor_h <= h["hour"] < max(ceil_h, floor_h + 1):
            matches.append(h)
    if not matches:
        return None
    avg = sum(m["score"] for m in matches) / len(matches)
    best = max(matches, key=lambda m: m["score"])
    return {"avg": avg, "best": best, "n": len(matches)}


# ──────────────────────────────────────────────────────────────
# 카드 빌더 헬퍼
# ──────────────────────────────────────────────────────────────
def make_card(parent: tk.Widget, bg: str = CARD) -> tk.Frame:
    return tk.Frame(parent, bg=bg, bd=0, highlightthickness=0)


def make_label(parent, text, font, fg=TEXT, bg=CARD, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg,
                    anchor="w", **kw)


# ──────────────────────────────────────────────────────────────
# 메인 앱
# ──────────────────────────────────────────────────────────────
class WalkFinderApp:
    def __init__(self, root: tk.Tk, data: dict, routes: dict):
        self.root = root
        self.data = data
        self.routes = routes
        self._setup_window()
        self._setup_fonts()
        self._build()

    def _setup_window(self) -> None:
        self.root.title("캠퍼스 산책지수")
        self.root.configure(bg=BG)
        self.root.geometry("1180x820")
        self.root.minsize(900, 640)

    def _setup_fonts(self) -> None:
        family = "Pretendard" if "Pretendard" in tkfont.families() else "Malgun Gothic"
        self.f_title  = tkfont.Font(family=family, size=20, weight="bold")
        self.f_h1     = tkfont.Font(family=family, size=14, weight="bold")
        self.f_h2     = tkfont.Font(family=family, size=12, weight="bold")
        self.f_body   = tkfont.Font(family=family, size=10)
        self.f_small  = tkfont.Font(family=family, size=9)
        self.f_big    = tkfont.Font(family=family, size=28, weight="bold")
        self.f_mid    = tkfont.Font(family=family, size=16, weight="bold")
        self.f_chip   = tkfont.Font(family=family, size=9, weight="bold")

    # ──────────────────────────────────────────────────────
    # 전체 레이아웃
    # ──────────────────────────────────────────────────────
    def _build(self) -> None:
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=18, pady=14)

        # 헤더
        self._build_hero(outer)

        # 좌/우 컬럼
        layout = tk.Frame(outer, bg=BG)
        layout.pack(fill="both", expand=True, pady=(10, 0))
        layout.grid_columnconfigure(0, weight=0, minsize=340)
        layout.grid_columnconfigure(1, weight=1)
        layout.grid_rowconfigure(0, weight=1)

        side = tk.Frame(layout, bg=BG)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        main = tk.Frame(layout, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")

        self._build_best_card(side)
        self._build_schedule_card(side)
        self._build_air_card(side)

        self._build_routes_panel(main)

        # 하단 시간대별
        self._build_hourly(outer)

        # 푸터
        self._build_footer(outer)

    # ──────────────────────────────────────────────────────
    # 헤더 (학교칩 + 타이틀)
    # ──────────────────────────────────────────────────────
    def _build_hero(self, parent: tk.Frame) -> None:
        chip = tk.Label(
            parent, text=f"  {self.data.get('school', '학교')}  ",
            font=self.f_chip, fg=PRIMARY, bg=PRIMARY_SOFT,
            padx=2, pady=2,
        )
        chip.pack(anchor="w")

        title = tk.Label(
            parent, text="오늘 산책 갈래?",
            font=self.f_title, fg=TEXT, bg=BG, anchor="w",
        )
        title.pack(anchor="w", pady=(6, 2))

        bt = self.data.get("best_time")
        sub_text = friend_message(bt["score"]) if bt else "오늘은 데이터가 부족해…"
        sub = tk.Label(
            parent, text=sub_text,
            font=self.f_body, fg=SUB, bg=BG, anchor="w",
        )
        sub.pack(anchor="w")

    # ──────────────────────────────────────────────────────
    # 좌측: 황금시간 카드
    # ──────────────────────────────────────────────────────
    def _build_best_card(self, parent: tk.Frame) -> None:
        bt = self.data.get("best_time")
        if not bt: return
        card = make_card(parent, bg=PRIMARY)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=PRIMARY)
        inner.pack(fill="x", padx=18, pady=14)

        tk.Label(inner, text="오늘 산책 황금시간",
                 font=self.f_chip, fg="white", bg=PRIMARY, anchor="w").pack(anchor="w")
        tk.Label(inner, text=f"{bt['hour']}시",
                 font=self.f_big, fg="white", bg=PRIMARY, anchor="w").pack(anchor="w", pady=(2, 4))
        tk.Label(inner, text=f"점수 {bt['score']}",
                 font=self.f_small, fg="white", bg=PRIMARY, anchor="w").pack(anchor="w")
        detail = (
            f"{bt['sky_text']} · {round(bt['tmp'])}° · "
            f"강수확률 {round(bt['pop'])}% · 풍속 {bt['wsd']}m/s"
        )
        tk.Label(inner, text=detail,
                 font=self.f_small, fg="white", bg=PRIMARY,
                 anchor="w", justify="left").pack(anchor="w", pady=(8, 0))

    # ──────────────────────────────────────────────────────
    # 좌측: 학교 일과 슬롯 카드
    # ──────────────────────────────────────────────────────
    def _build_schedule_card(self, parent: tk.Frame) -> None:
        schedule = self.routes.get("schedule", [])
        if not schedule: return
        card = make_card(parent)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(inner, text="오늘의 산책 슬롯",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(inner, text="학교 일과 기준 · 평균 점수와 베스트 시각",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 8))

        # 베스트 슬롯 찾기
        results = []
        for slot in schedule:
            r = slot_match(self.data["hourly"], slot)
            results.append((slot, r))
        valid = [(s, r) for s, r in results if r]
        best_id = max(valid, key=lambda x: x[1]["avg"])[0]["id"] if valid else None

        for slot, result in results:
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", pady=2)

            if result:
                fg, bg = score_color(result["avg"])
                score_text = str(round(result["avg"]))
                sub_text = (
                    f"{slot['start']}~{slot['end']} · 베스트 {result['best']['hour']}시"
                    f" · {result['best']['sky_text']} {round(result['best']['tmp'])}°"
                )
            else:
                fg, bg = SUB, BG
                score_text = "—"
                sub_text = f"{slot['start']}~{slot['end']} · 데이터 없음 (지난 시간 또는 예보 범위 밖)"

            box = tk.Frame(row, bg=bg, bd=0, highlightthickness=1, highlightbackground=fg)
            box.pack(fill="x")

            inner_box = tk.Frame(box, bg=bg)
            inner_box.pack(fill="x", padx=10, pady=8)
            inner_box.grid_columnconfigure(1, weight=1)

            icon = tk.Label(inner_box, text=slot.get("icon", "•"),
                            font=self.f_h1, bg=bg)
            icon.grid(row=0, column=0, rowspan=2, padx=(0, 8))

            label_line = tk.Frame(inner_box, bg=bg)
            label_line.grid(row=0, column=1, sticky="w")
            tk.Label(label_line, text=slot["label"],
                     font=self.f_h2, fg=TEXT, bg=bg).pack(side="left")
            tk.Label(label_line, text=f"  {slot['start']}~{slot['end']}",
                     font=self.f_small, fg=SUB, bg=bg).pack(side="left")
            if best_id and slot["id"] == best_id and result:
                tk.Label(label_line, text="  추천", font=self.f_small,
                         fg="white", bg=PRIMARY, padx=6).pack(side="left", padx=(4, 0))

            tk.Label(inner_box, text=sub_text,
                     font=self.f_small, fg=SUB, bg=bg, anchor="w").grid(row=1, column=1, sticky="w")

            tk.Label(inner_box, text=score_text,
                     font=self.f_mid, fg=fg, bg=bg).grid(row=0, column=2, rowspan=2, padx=(8, 0))

    # ──────────────────────────────────────────────────────
    # 좌측: 미세먼지 카드
    # ──────────────────────────────────────────────────────
    def _build_air_card(self, parent: tk.Frame) -> None:
        air = self.data.get("air", {})
        card = make_card(parent)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x")

        col1 = tk.Frame(row, bg=CARD); col1.pack(side="left", expand=True, fill="x")
        tk.Label(col1, text="미세먼지 (PM10)", font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w")
        pm10_text = "—" if air.get("pm10", -1) < 0 else f"{air['pm10']} ㎍/㎥"
        tk.Label(col1, text=pm10_text, font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")

        col2 = tk.Frame(row, bg=CARD); col2.pack(side="left", expand=True, fill="x")
        tk.Label(col2, text="초미세먼지 (PM2.5)", font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w")
        pm25_text = "—" if air.get("pm25", -1) < 0 else f"{air['pm25']} ㎍/㎥"
        tk.Label(col2, text=pm25_text, font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")

        label = air.get("label", "—")
        fg, bg = air_label_to_color(label)
        badge = tk.Label(inner, text=f"  {label}  ",
                         font=self.f_chip, fg=fg, bg=bg, padx=4, pady=2)
        badge.pack(anchor="w", pady=(10, 0))

        meta = f"{air.get('station', '-') } · {air.get('measured_at', '')}"
        tk.Label(inner, text=meta,
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(4, 0))

    # ──────────────────────────────────────────────────────
    # 우측: 추천 코스 패널
    # ──────────────────────────────────────────────────────
    def _build_routes_panel(self, parent: tk.Frame) -> None:
        card = make_card(parent)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(inner, text="캠퍼스 산책 코스",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(inner, text="기숙사 학생용 · 학교 안에서만 도는 코스",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 10))

        score = (self.data.get("best_time") or {}).get("score", 0)
        routes = [r for r in self.routes.get("routes", []) if not r.get("_placeholder")]

        if not routes:
            tk.Label(inner, text="등록된 추천 코스가 없어요.\n"
                                  "웹페이지(index.html)의 '코스 그리기'로 추가하세요.",
                     font=self.f_body, fg=SUB, bg=CARD, justify="left").pack(anchor="w", pady=20)
            return

        for r in routes:
            recommended = score >= r.get("min_score", 0)
            row_bg = GOOD_SOFT if recommended else BG
            row = tk.Frame(inner, bg=row_bg, highlightthickness=1,
                           highlightbackground=r.get("color", PRIMARY))
            row.pack(fill="x", pady=4)

            inner_row = tk.Frame(row, bg=row_bg)
            inner_row.pack(fill="x", padx=12, pady=10)
            inner_row.grid_columnconfigure(1, weight=1)

            dot = tk.Canvas(inner_row, width=14, height=14, bg=row_bg, highlightthickness=0)
            dot.create_oval(2, 2, 12, 12, fill=r.get("color", PRIMARY), outline="")
            dot.grid(row=0, column=0, rowspan=2, padx=(0, 10))

            title_line = tk.Frame(inner_row, bg=row_bg)
            title_line.grid(row=0, column=1, sticky="w")
            tk.Label(title_line, text=r["name"], font=self.f_h2,
                     fg=TEXT, bg=row_bg).pack(side="left")
            if recommended:
                tk.Label(title_line, text="  추천  ", font=self.f_small,
                         fg="white", bg=GOOD).pack(side="left", padx=(6, 0))

            tk.Label(inner_row, text=r.get("subtitle", ""),
                     font=self.f_small, fg=SUB, bg=row_bg, anchor="w") \
                .grid(row=1, column=1, sticky="w")

            meta = f"{r.get('duration_min', '?')}분 · {r.get('distance_km', '?')}km"
            tk.Label(inner_row, text=meta, font=self.f_small,
                     fg=SUB, bg=row_bg).grid(row=0, column=2, rowspan=2, padx=(8, 0))

    # ──────────────────────────────────────────────────────
    # 하단: 시간대별 점수 그리드
    # ──────────────────────────────────────────────────────
    def _build_hourly(self, parent: tk.Frame) -> None:
        card = make_card(parent)
        card.pack(fill="x", pady=(10, 0))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(inner, text="시간대별 산책지수",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(inner, text="초록일수록 산책 좋은 시간",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 8))

        hourly = self.data.get("hourly", [])
        grid = tk.Frame(inner, bg=CARD)
        grid.pack(fill="x")

        cols = 12
        for i, h in enumerate(hourly):
            r = i // cols
            c = i % cols
            grid.grid_columnconfigure(c, weight=1)
            fg, bg = score_color(h["score"])
            cell = tk.Frame(grid, bg=bg, highlightthickness=1, highlightbackground=fg)
            cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)

            tk.Label(cell, text=f"{h['hour']}시", font=self.f_small,
                     fg=SUB, bg=bg).pack(pady=(6, 0))
            tk.Label(cell, text=str(round(h["score"])), font=self.f_h1,
                     fg=fg, bg=bg).pack()
            tk.Label(cell, text=f"{round(h['tmp'])}° · {h['sky_text']}",
                     font=self.f_small, fg=SUB, bg=bg).pack(pady=(0, 6))

    # ──────────────────────────────────────────────────────
    # 푸터: 데이터 출처
    # ──────────────────────────────────────────────────────
    def _build_footer(self, parent: tk.Frame) -> None:
        sep = tk.Frame(parent, bg=LINE, height=1)
        sep.pack(fill="x", pady=(10, 8))

        foot = tk.Frame(parent, bg=BG)
        foot.pack(fill="x")

        tk.Label(foot, text="데이터 출처",
                 font=self.f_h2, fg=TEXT, bg=BG, anchor="w").pack(anchor="w")
        for src in [
            "· 기상청 _ 단기예보 조회서비스 (공공데이터포털)",
            "· 한국환경공단 _ 에어코리아 _ 대기오염정보 (공공데이터포털)",
            "· 위성 영상: Esri, Maxar, Earthstar Geographics, GIS User Community",
            "· 일반 지도: OpenStreetMap contributors",
        ]:
            tk.Label(foot, text=src, font=self.f_small, fg=SUB, bg=BG, anchor="w").pack(anchor="w")

        tk.Label(foot, text=f"업데이트 · {self.data.get('generated_at', '-').replace('T',' ')}",
                 font=self.f_small, fg=SUB, bg=BG, anchor="w").pack(anchor="w", pady=(6, 0))


# ──────────────────────────────────────────────────────────────
# 실행 진입점
# ──────────────────────────────────────────────────────────────
def main() -> int:
    base_dir = Path(__file__).resolve().parent
    try:
        data = load_json(base_dir / "data.json")
        routes = load_json(base_dir / "routes.json")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    root = tk.Tk()
    WalkFinderApp(root, data, routes)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
