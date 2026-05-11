"""
캠퍼스 산책지수 - 데스크톱 GUI
================================================
index.html 페이지와 같은 정보를 tkinter 윈도우로 보여줍니다.
지도는 tkintermapview 로 Esri 위성 타일을 띄우고, '데이터 갱신' 버튼을
누르면 fetch_data.py 가 실행되어 공공데이터 API 가 다시 호출됩니다.

화면 구성 (HTML 페이지와 동일):
  ┌────────────────────────────────────────────┐
  │ 헤더 · 학교칩 · 타이틀 · [데이터 갱신] 버튼│
  ├────────────┬───────────────────────────────┤
  │ 좌측        │ 우측                          │
  │ - 황금시간  │ - 위성 지도 (학교 마커+코스) │
  │ - 산책 슬롯│ - 추천 코스 목록             │
  │ - 미세먼지  │                              │
  ├────────────┴───────────────────────────────┤
  │ 하단 · 시간대별 점수 그리드                │
  ├────────────────────────────────────────────┤
  │ 푸터 · 데이터 출처                         │
  └────────────────────────────────────────────┘

실행:  py app.py
요구사항: data.json, routes.json (먼저 fetch_data.py 실행 필요)
            tkintermapview 패키지 (지도용)
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox


# ──────────────────────────────────────────────────────────────
# 색상 (style.css 와 동일)
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
PALETTE     = ["#1ec979", "#3182f6", "#ff8c42", "#ff5c5c", "#9b59ff", "#00bcd4"]


def score_color(score: float) -> tuple[str, str]:
    if score >= 80: return GOOD, GOOD_SOFT
    if score >= 60: return PRIMARY, PRIMARY_SOFT
    if score >= 40: return "#b07a00", WARN_SOFT
    return BAD, BAD_SOFT


def air_color(label: str) -> tuple[str, str]:
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


def parse_hhmm(s: str) -> float:
    h, m = (int(x) for x in s.split(":"))
    return h + m / 60


def slot_match(hourly: list[dict], slot: dict) -> dict | None:
    start = parse_hhmm(slot["start"])
    end = parse_hhmm(slot["end"])
    floor_h = int(start)
    ceil_h = int(end) if end == int(end) else int(end) + 1
    now = datetime.now()
    matches = []
    for h in hourly:
        try:
            dt = datetime.fromisoformat(h["datetime"])
        except Exception:
            continue
        if dt < now:
            continue
        if floor_h <= h["hour"] < max(ceil_h, floor_h + 1):
            matches.append(h)
    if not matches:
        return None
    avg = sum(m["score"] for m in matches) / len(matches)
    best = max(matches, key=lambda m: m["score"])
    return {"avg": avg, "best": best, "n": len(matches)}


# ──────────────────────────────────────────────────────────────
# 메인 앱
# ──────────────────────────────────────────────────────────────
class WalkFinderApp:
    def __init__(self, root: tk.Tk, base_dir: Path):
        self.root = root
        self.base_dir = base_dir
        self.data: dict = {}
        self.routes: dict = {}
        self._refreshing = False

        self._setup_window()
        self._setup_fonts()
        self._setup_scrollable()

        self._load_artifacts()
        self._build_all()

    # ── 스크롤 가능한 메인 컨테이너 ──
    def _setup_scrollable(self) -> None:
        container = tk.Frame(self.root, bg=BG)
        container.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical",
                          command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.outer = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self.outer, anchor="nw")

        def _on_outer_resize(_e):
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        def _on_canvas_resize(e):
            self._canvas.itemconfig(self._canvas_window, width=e.width)
        self.outer.bind("<Configure>", _on_outer_resize)
        self._canvas.bind("<Configure>", _on_canvas_resize)

        # 마우스 휠: 지도 위에서는 무시 (지도 자체 줌 양보)
        def _on_wheel(e):
            if getattr(self, "map_widget", None) is not None:
                mw = self.map_widget
                try:
                    mx = mw.winfo_rootx(); my = mw.winfo_rooty()
                    mw_w = mw.winfo_width(); mw_h = mw.winfo_height()
                    if mx <= e.x_root < mx + mw_w and my <= e.y_root < my + mw_h:
                        return
                except Exception:
                    pass
            self._canvas.yview_scroll(int(-e.delta / 120), "units")
        self._canvas.bind_all("<MouseWheel>", _on_wheel)

        # outer 내부 padding 효과
        self.outer.configure(padx=14, pady=12)

    # ── 윈도우 / 폰트 ──
    def _setup_window(self) -> None:
        self.root.title("캠퍼스 산책지수")
        self.root.configure(bg=BG)

        # 화면 크기에 맞춰 위치/크기 자동 조정 + 가운데 정렬
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(1280, sw - 80)
        h = min(880, sh - 120)
        x = max(20, (sw - w) // 2)
        y = max(20, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(900, 640)

        # 창을 다른 창 위로 끌어올림 (잠깐 topmost → 풀기)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))

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
        self.f_btn    = tkfont.Font(family=family, size=10, weight="bold")

    # ── 데이터 로드 / 새로고침 ──
    def _load_artifacts(self) -> None:
        try:
            self.data = json.loads(
                (self.base_dir / "data.json").read_text(encoding="utf-8"))
            self.routes = json.loads(
                (self.base_dir / "routes.json").read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            messagebox.showerror(
                "데이터 없음",
                f"{e}\n\n먼저 'py fetch_data.py' 를 실행해 주세요.",
            )
            sys.exit(1)

    def refresh_from_api(self) -> None:
        """[데이터 갱신] 버튼 처리 — 백그라운드에서 fetch_data.py 실행."""
        if self._refreshing:
            return
        self._refreshing = True
        self.refresh_btn.config(text="갱신중...", state="disabled", bg=SUB)

        def worker():
            try:
                env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
                result = subprocess.run(
                    [sys.executable, str(self.base_dir / "fetch_data.py")],
                    cwd=str(self.base_dir),
                    capture_output=True, text=True, env=env, timeout=30,
                )
                ok = result.returncode == 0
                err = result.stderr if not ok else ""
            except Exception as e:
                ok, err = False, str(e)
            self.root.after(0, lambda: self._on_refresh_done(ok, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(self, ok: bool, err: str) -> None:
        self._refreshing = False
        self.refresh_btn.config(text="데이터 갱신", state="normal", bg=PRIMARY)
        if ok:
            self._load_artifacts()
            for child in self.outer.winfo_children():
                child.destroy()
            self._build_all()
        else:
            messagebox.showerror("갱신 실패", err or "알 수 없는 오류")

    # ──────────────────────────────────────────────────────
    # 전체 레이아웃
    # ──────────────────────────────────────────────────────
    def _build_all(self) -> None:
        self._build_hero(self.outer)

        layout = tk.Frame(self.outer, bg=BG)
        layout.pack(fill="both", expand=True, pady=(8, 0))
        layout.grid_columnconfigure(0, weight=0, minsize=320)
        layout.grid_columnconfigure(1, weight=1)
        layout.grid_rowconfigure(0, weight=1)

        side = tk.Frame(layout, bg=BG)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        main = tk.Frame(layout, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")

        self._build_best_card(side)
        self._build_schedule_card(side)
        self._build_air_card(side)

        self._build_map(main)
        self._build_routes_panel(main)

        self._build_hourly(self.outer)
        self._build_footer(self.outer)

    # ── 헤더 ──
    def _build_hero(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG)
        bar.pack(fill="x")

        left = tk.Frame(bar, bg=BG)
        left.pack(side="left", fill="x", expand=True)

        chip = tk.Label(
            left, text=f"  {self.data.get('school', '학교')}  ",
            font=self.f_chip, fg=PRIMARY, bg=PRIMARY_SOFT, padx=2, pady=2,
        )
        chip.pack(anchor="w")
        tk.Label(left, text="오늘 산책 갈래?",
                 font=self.f_title, fg=TEXT, bg=BG, anchor="w").pack(anchor="w", pady=(4, 2))
        bt = self.data.get("best_time")
        sub = friend_message(bt["score"]) if bt else "오늘은 데이터가 부족해…"
        tk.Label(left, text=sub, font=self.f_body, fg=SUB, bg=BG, anchor="w").pack(anchor="w")

        # 데이터 갱신 버튼 (API 호출)
        self.refresh_btn = tk.Button(
            bar, text="데이터 갱신", font=self.f_btn,
            fg="white", bg=PRIMARY, activebackground="#2670d8",
            activeforeground="white", relief="flat",
            padx=14, pady=8, cursor="hand2",
            command=self.refresh_from_api,
        )
        self.refresh_btn.pack(side="right", anchor="ne")

    # ── 황금시간 카드 ──
    def _build_best_card(self, parent: tk.Frame) -> None:
        bt = self.data.get("best_time")
        if not bt:
            return
        card = tk.Frame(parent, bg=PRIMARY)
        card.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(card, bg=PRIMARY)
        inner.pack(fill="x", padx=16, pady=12)

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
        tk.Label(inner, text=detail, font=self.f_small, fg="white",
                 bg=PRIMARY, anchor="w", justify="left").pack(anchor="w", pady=(6, 0))

    # ── 슬롯 카드 ──
    def _build_schedule_card(self, parent: tk.Frame) -> None:
        schedule = self.routes.get("schedule", [])
        if not schedule:
            return
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="오늘의 산책 슬롯",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(inner, text="학교 일과 기준 · 평균 점수와 베스트 시각",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 6))

        results = [(s, slot_match(self.data.get("hourly", []), s)) for s in schedule]
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
                sub_text = f"{slot['start']}~{slot['end']} · 데이터 없음"

            box = tk.Frame(row, bg=bg, bd=0, highlightthickness=1, highlightbackground=fg)
            box.pack(fill="x")
            inner_box = tk.Frame(box, bg=bg)
            inner_box.pack(fill="x", padx=10, pady=7)
            inner_box.grid_columnconfigure(1, weight=1)

            tk.Label(inner_box, text=slot.get("icon", "•"),
                     font=self.f_h1, bg=bg).grid(row=0, column=0, rowspan=2, padx=(0, 8))

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

    # ── 미세먼지 카드 ──
    def _build_air_card(self, parent: tk.Frame) -> None:
        air = self.data.get("air", {})
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)

        row = tk.Frame(inner, bg=CARD); row.pack(fill="x")
        col1 = tk.Frame(row, bg=CARD); col1.pack(side="left", expand=True, fill="x")
        tk.Label(col1, text="미세먼지 (PM10)",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w")
        pm10 = "—" if air.get("pm10", -1) < 0 else f"{air['pm10']} ㎍/㎥"
        tk.Label(col1, text=pm10, font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")

        col2 = tk.Frame(row, bg=CARD); col2.pack(side="left", expand=True, fill="x")
        tk.Label(col2, text="초미세먼지 (PM2.5)",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w")
        pm25 = "—" if air.get("pm25", -1) < 0 else f"{air['pm25']} ㎍/㎥"
        tk.Label(col2, text=pm25, font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")

        label = air.get("label", "—")
        fg, bg = air_color(label)
        tk.Label(inner, text=f"  {label}  ",
                 font=self.f_chip, fg=fg, bg=bg, padx=4, pady=2).pack(anchor="w", pady=(8, 0))

        meta = f"{air.get('station', '-')} · {air.get('measured_at', '')}"
        tk.Label(inner, text=meta, font=self.f_small, fg=SUB, bg=CARD,
                 anchor="w").pack(anchor="w", pady=(4, 0))

    # ── 지도 ──
    def _build_map(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill="both", expand=True, pady=(0, 8))

        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(head, text="캠퍼스 산책 코스",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(head, text="기숙사 학생용 · 학교 안에서만 도는 코스 · Esri 위성",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w")

        try:
            from tkintermapview import TkinterMapView
        except ImportError:
            tk.Label(card, text="(지도 위젯 사용을 위해 'py -m pip install tkintermapview' 실행 필요)",
                     font=self.f_small, fg=BAD, bg=CARD).pack(padx=12, pady=20)
            return

        school = self.routes.get("school", {})
        lat = school.get("lat", 36.01444)
        lon = school.get("lon", 127.03556)

        mv = TkinterMapView(card, width=600, height=320, corner_radius=10)
        mv.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        mv.set_tile_server(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            max_zoom=19,
        )
        mv.set_position(lat, lon)
        mv.set_zoom(18)

        # 학교 마커
        mv.set_marker(lat, lon, text=school.get("name", "학교"),
                      marker_color_circle=PRIMARY,
                      marker_color_outside="#ffffff",
                      text_color="#ffffff", font=("Malgun Gothic", 9, "bold"))

        # 코스 폴리라인
        score = (self.data.get("best_time") or {}).get("score", 0)
        for i, r in enumerate(self.routes.get("routes", [])):
            if r.get("_placeholder"):
                continue
            color = r.get("color") or PALETTE[i % len(PALETTE)]
            recommended = score >= r.get("min_score", 0)
            path = [(p[0], p[1]) for p in r.get("path", [])]
            if len(path) >= 2:
                mv.set_path(path, color=color,
                            width=5 if recommended else 3)

        self.map_widget = mv

    # ── 코스 리스트 ──
    def _build_routes_panel(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="추천 코스",
                 font=self.f_h2, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 4))

        score = (self.data.get("best_time") or {}).get("score", 0)
        routes = [r for r in self.routes.get("routes", []) if not r.get("_placeholder")]

        if not routes:
            tk.Label(inner, text="등록된 추천 코스가 없습니다.",
                     font=self.f_small, fg=SUB, bg=CARD).pack(anchor="w", pady=8)
            return

        for i, r in enumerate(routes):
            color = r.get("color") or PALETTE[i % len(PALETTE)]
            recommended = score >= r.get("min_score", 0)
            row_bg = GOOD_SOFT if recommended else BG
            row = tk.Frame(inner, bg=row_bg, highlightthickness=1, highlightbackground=color)
            row.pack(fill="x", pady=3)
            ir = tk.Frame(row, bg=row_bg); ir.pack(fill="x", padx=10, pady=8)
            ir.grid_columnconfigure(1, weight=1)

            dot = tk.Canvas(ir, width=14, height=14, bg=row_bg, highlightthickness=0)
            dot.create_oval(2, 2, 12, 12, fill=color, outline="")
            dot.grid(row=0, column=0, rowspan=2, padx=(0, 10))

            tline = tk.Frame(ir, bg=row_bg); tline.grid(row=0, column=1, sticky="w")
            tk.Label(tline, text=r["name"], font=self.f_h2,
                     fg=TEXT, bg=row_bg).pack(side="left")
            if recommended:
                tk.Label(tline, text="  추천  ", font=self.f_small,
                         fg="white", bg=GOOD).pack(side="left", padx=(6, 0))

            tk.Label(ir, text=r.get("subtitle", ""),
                     font=self.f_small, fg=SUB, bg=row_bg, anchor="w") \
                .grid(row=1, column=1, sticky="w")
            meta = f"{r.get('duration_min', '?')}분 · {r.get('distance_km', '?')}km"
            tk.Label(ir, text=meta, font=self.f_small,
                     fg=SUB, bg=row_bg).grid(row=0, column=2, rowspan=2, padx=(8, 0))

    # ── 시간대별 그리드 ──
    def _build_hourly(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill="x", pady=(8, 0))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="시간대별 산책지수",
                 font=self.f_h1, fg=TEXT, bg=CARD, anchor="w").pack(anchor="w")
        tk.Label(inner, text="초록일수록 산책 좋은 시간",
                 font=self.f_small, fg=SUB, bg=CARD, anchor="w").pack(anchor="w", pady=(0, 6))

        hourly = self.data.get("hourly", [])
        grid = tk.Frame(inner, bg=CARD); grid.pack(fill="x")

        cols = 12
        for i, h in enumerate(hourly):
            r, c = divmod(i, cols)
            grid.grid_columnconfigure(c, weight=1)
            fg, bg = score_color(h["score"])
            cell = tk.Frame(grid, bg=bg, highlightthickness=1, highlightbackground=fg)
            cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
            tk.Label(cell, text=f"{h['hour']}시", font=self.f_small,
                     fg=SUB, bg=bg).pack(pady=(5, 0))
            tk.Label(cell, text=str(round(h["score"])), font=self.f_h1,
                     fg=fg, bg=bg).pack()
            tk.Label(cell, text=f"{round(h['tmp'])}° · {h['sky_text']}",
                     font=self.f_small, fg=SUB, bg=bg).pack(pady=(0, 5))

    # ── 푸터 ──
    def _build_footer(self, parent: tk.Frame) -> None:
        sep = tk.Frame(parent, bg=LINE, height=1); sep.pack(fill="x", pady=(8, 6))
        foot = tk.Frame(parent, bg=BG); foot.pack(fill="x")
        tk.Label(foot, text="데이터 출처",
                 font=self.f_h2, fg=TEXT, bg=BG, anchor="w").pack(anchor="w")
        for src in [
            "· 기상청 _ 단기예보 조회서비스 (공공데이터포털)",
            "· 한국환경공단 _ 에어코리아 _ 대기오염정보 (공공데이터포털)",
            "· 위성 영상: Esri, Maxar, Earthstar Geographics, GIS User Community",
        ]:
            tk.Label(foot, text=src, font=self.f_small, fg=SUB, bg=BG, anchor="w").pack(anchor="w")
        tk.Label(foot,
                 text=f"업데이트 · {self.data.get('generated_at','-').replace('T',' ')}",
                 font=self.f_small, fg=SUB, bg=BG, anchor="w").pack(anchor="w", pady=(4, 0))


# ──────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────
def main() -> int:
    base_dir = Path(__file__).resolve().parent
    root = tk.Tk()
    WalkFinderApp(root, base_dir)

    if "--capture" in sys.argv:
        def _capture():
            try:
                from PIL import ImageGrab
                root.update_idletasks(); root.update()
                x = root.winfo_rootx(); y = root.winfo_rooty()
                w = root.winfo_width(); h = root.winfo_height()
                shots = base_dir / "screenshots"
                shots.mkdir(exist_ok=True)
                ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(shots / "app.png")
                print(f"[OK] {shots / 'app.png'}")
            except Exception as e:
                print(f"[ERR] app 캡처 실패: {e}", file=sys.stderr)
            finally:
                root.after(100, root.destroy)
        # 지도 타일 로딩 시간 + 그리드 렌더 시간 확보
        root.after(3000, _capture)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
