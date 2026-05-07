"""
산책 시간 추천기 - 데이터 수집 스크립트
================================================

공공데이터포털의 두 가지 API를 결합해 우리 학교 주변의
시간대별 '산책 적합도 지수'를 계산하고 data.json 으로 저장합니다.

사용 API:
  1) 기상청_단기예보 조회서비스
     - 기온, 강수확률, 풍속, 하늘상태, 습도
  2) 한국환경공단_에어코리아_대기오염정보
     - 미세먼지(PM10), 초미세먼지(PM2.5)

산책지수 = 기상 점수(50) + 대기 점수(50)
실행:  py fetch_data.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# 윈도우 PowerShell 콘솔에서 한글이 깨지지 않도록 UTF-8 출력 강제
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# 학교 위치 (전북과학고등학교, 전북 익산시 금마면 용순신기길 48-69)
# 출처: 위키백과 - 전북과학고등학교
# ──────────────────────────────────────────────────────────────
SCHOOL_NAME = "전북과학고등학교"
SCHOOL_LAT = 36.01444
SCHOOL_LON = 127.03556

# 미세먼지 측정소: 익산시 8개 측정소 중 학교(금마면)와 동일 행정동인 '금마면' 측정소
SIDO_NAME = "전북"  # 에어코리아 시도명은 약칭 사용 (전북특별자치도 X)
STATION_NAME = "금마면"  # 학교 위치와 동일 행정동의 도시대기 측정소


# ──────────────────────────────────────────────────────────────
# 위경도 → 기상청 격자(nx, ny) 변환
# 출처: 기상청 공식 LCC DFS 변환 공식
# ──────────────────────────────────────────────────────────────
def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    RE = 6371.00877
    GRID = 5.0
    SLAT1, SLAT2 = 30.0, 60.0
    OLON, OLAT = 126.0, 38.0
    XO, YO = 43, 136

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


# ──────────────────────────────────────────────────────────────
# .env 로딩 (외부 라이브러리 없이)
# ──────────────────────────────────────────────────────────────
def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


# ──────────────────────────────────────────────────────────────
# HTTP GET (urllib만 사용 → 외부 패키지 불필요)
# ──────────────────────────────────────────────────────────────
def http_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": "walk-finder/1.0"})
    with urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 일부 API는 오류 시 XML/HTML 반환. 앞부분 보여주고 종료.
        print("[ERROR] API 응답이 JSON이 아닙니다. 응답 일부:", file=sys.stderr)
        print(raw[:500], file=sys.stderr)
        raise


# ──────────────────────────────────────────────────────────────
# 기상청 단기예보 조회
# ──────────────────────────────────────────────────────────────
def fetch_weather(service_key: str, nx: int, ny: int) -> list[dict[str, Any]]:
    """가장 최근 발표된 단기예보를 가져와 시간대별로 정리."""
    # 단기예보 발표 시각: 02, 05, 08, 11, 14, 17, 20, 23시 (10분 후 제공)
    now = datetime.now()
    base_times = [23, 20, 17, 14, 11, 8, 5, 2]
    base_date = now.strftime("%Y%m%d")
    base_time = "0200"
    chosen = None
    for bt in base_times:
        candidate = now.replace(hour=bt, minute=10, second=0, microsecond=0)
        if candidate <= now:
            chosen = candidate
            break
    if chosen is None:
        # 새벽 02:10 이전 → 전날 23시 발표 사용
        chosen = (now - timedelta(days=1)).replace(hour=23, minute=10, second=0, microsecond=0)
    base_date = chosen.strftime("%Y%m%d")
    base_time = chosen.strftime("%H%M")[:2] + "00"

    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1000,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }
    data = http_get_json(url, params)
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not items:
        raise RuntimeError(f"기상청 응답에 예보 항목이 없습니다: {data}")

    # category 별로 (fcstDate, fcstTime) → value 매핑
    by_time: dict[str, dict[str, str]] = {}
    for item in items:
        key = f"{item['fcstDate']}{item['fcstTime']}"
        by_time.setdefault(key, {})[item["category"]] = item["fcstValue"]

    # 오늘 기준 앞으로 24시간 분량만 추리기
    result: list[dict[str, Any]] = []
    for key in sorted(by_time.keys()):
        d = datetime.strptime(key, "%Y%m%d%H%M")
        if d < now.replace(minute=0, second=0, microsecond=0):
            continue
        if d > now + timedelta(hours=24):
            break
        c = by_time[key]
        try:
            result.append({
                "datetime": d.isoformat(),
                "hour": d.hour,
                "tmp": float(c.get("TMP", 0)),       # 기온(℃)
                "pop": float(c.get("POP", 0)),       # 강수확률(%)
                "wsd": float(c.get("WSD", 0)),       # 풍속(m/s)
                "reh": float(c.get("REH", 0)),       # 습도(%)
                "sky": int(c.get("SKY", 1)),         # 1맑음 3구름많음 4흐림
                "pty": int(c.get("PTY", 0)),         # 0없음 1비 2비/눈 3눈 4소나기
            })
        except (ValueError, TypeError):
            continue

    # 23시(전날 마지막 시간) 데이터는 그리드 정렬상 어색하므로 제외하여
    # 0시부터 깔끔하게 시작하도록 정리
    if result and result[0]["hour"] == 23:
        result.pop(0)
    return result


# ──────────────────────────────────────────────────────────────
# 에어코리아 대기오염정보 조회
# ──────────────────────────────────────────────────────────────
def fetch_air(service_key: str) -> dict[str, float]:
    """현재 측정소의 PM10, PM2.5 값을 가져옴."""
    url = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
    params = {
        "serviceKey": service_key,
        "returnType": "json",
        "numOfRows": 1,
        "pageNo": 1,
        "stationName": STATION_NAME,
        "dataTerm": "DAILY",
        "ver": "1.3",
    }
    data = http_get_json(url, params)
    items = data.get("response", {}).get("body", {}).get("items", [])
    if not items:
        # 측정소명 검색 실패 시 시도별 조회로 폴백
        return fetch_air_by_sido(service_key)

    item = items[0]
    pm10 = _parse_float(item.get("pm10Value"))
    pm25 = _parse_float(item.get("pm25Value"))
    return {
        "pm10": pm10,
        "pm25": pm25,
        "station": STATION_NAME,
        "measured_at": item.get("dataTime", ""),
    }


def fetch_air_by_sido(service_key: str) -> dict[str, float]:
    url = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
    params = {
        "serviceKey": service_key,
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "sidoName": SIDO_NAME,
        "ver": "1.3",
    }
    data = http_get_json(url, params)
    items = data.get("response", {}).get("body", {}).get("items", [])
    # 익산시 측정소를 우선
    target = None
    for it in items:
        if "익산" in (it.get("stationName") or ""):
            target = it
            break
    if target is None and items:
        target = items[0]
    if target is None:
        return {"pm10": -1, "pm25": -1, "station": "정보 없음", "measured_at": ""}
    return {
        "pm10": _parse_float(target.get("pm10Value")),
        "pm25": _parse_float(target.get("pm25Value")),
        "station": target.get("stationName", ""),
        "measured_at": target.get("dataTime", ""),
    }


def _parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


# ──────────────────────────────────────────────────────────────
# 산책지수 계산
# ──────────────────────────────────────────────────────────────
def air_score(pm10: float, pm25: float) -> tuple[float, str]:
    """대기 점수(0~50). 환경부 기준 등급에 맞춰 매핑."""
    if pm10 < 0 or pm25 < 0:
        return 25.0, "측정값 없음"

    # PM10 등급: 0~30 좋음, 31~80 보통, 81~150 나쁨, 151+ 매우나쁨
    # PM2.5 등급: 0~15 좋음, 16~35 보통, 36~75 나쁨, 76+ 매우나쁨
    def grade(v: float, thresholds: list[float]) -> int:
        for i, t in enumerate(thresholds):
            if v <= t:
                return i  # 0=좋음 ... 3=매우나쁨
        return 3

    g10 = grade(pm10, [30, 80, 150])
    g25 = grade(pm25, [15, 35, 75])
    worst = max(g10, g25)
    # 점수: 좋음 50, 보통 38, 나쁨 18, 매우나쁨 5
    score_table = [50, 38, 18, 5]
    label_table = ["좋음", "보통", "나쁨", "매우나쁨"]
    return float(score_table[worst]), label_table[worst]


def weather_score(w: dict[str, Any]) -> tuple[float, str]:
    """기상 점수(0~50). 기온/강수/풍속/하늘상태를 합쳐 평가."""
    score = 50.0
    notes: list[str] = []

    tmp = w["tmp"]
    if 15 <= tmp <= 22:
        pass
    elif 10 <= tmp < 15 or 22 < tmp <= 26:
        score -= 5
    elif 5 <= tmp < 10 or 26 < tmp <= 30:
        score -= 12
        notes.append("조금 춥거나 더움")
    else:
        score -= 22
        notes.append("기온 부담")

    pop = w["pop"]
    pty = w["pty"]
    if pty != 0:
        score -= 30
        notes.append("강수 중")
    elif pop >= 60:
        score -= 18
        notes.append("비 올 가능성 큼")
    elif pop >= 30:
        score -= 8
        notes.append("우산 챙기는 게 안전")

    wsd = w["wsd"]
    if wsd >= 9:
        score -= 12
        notes.append("바람 강함")
    elif wsd >= 5:
        score -= 5

    sky = w["sky"]
    if sky == 4:
        score -= 3  # 흐림 약간 감점

    score = max(0.0, min(50.0, score))
    note = ", ".join(notes) if notes else "산책 좋음"
    return score, note


SKY_TEXT = {1: "맑음", 3: "구름많음", 4: "흐림"}
PTY_TEXT = {0: "없음", 1: "비", 2: "비/눈", 3: "눈", 4: "소나기"}


def build_recommendations(
    weather: list[dict[str, Any]], air: dict[str, float]
) -> dict[str, Any]:
    a_score, a_label = air_score(air["pm10"], air["pm25"])
    hourly: list[dict[str, Any]] = []
    for w in weather:
        w_score, w_note = weather_score(w)
        total = round(w_score + a_score, 1)
        hourly.append({
            "datetime": w["datetime"],
            "hour": w["hour"],
            "score": total,
            "weather_score": round(w_score, 1),
            "air_score": round(a_score, 1),
            "tmp": w["tmp"],
            "pop": w["pop"],
            "wsd": w["wsd"],
            "reh": w["reh"],
            "sky_text": SKY_TEXT.get(w["sky"], "정보없음"),
            "pty_text": PTY_TEXT.get(w["pty"], "정보없음"),
            "note": w_note,
        })

    # 학생들의 일과를 고려해 의미 있는 시간대만 추천 후보로
    daytime = [h for h in hourly if 6 <= h["hour"] <= 21]
    best = max(daytime, key=lambda x: x["score"]) if daytime else None

    return {
        "school": SCHOOL_NAME,
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "air": {
            "pm10": air["pm10"],
            "pm25": air["pm25"],
            "label": a_label,
            "station": air.get("station", ""),
            "measured_at": air.get("measured_at", ""),
        },
        "best_time": best,
        "hourly": hourly,
    }


# ──────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────
def print_report(result: dict[str, Any], routes_data: dict[str, Any] | None) -> None:
    """콘솔에 산책지수 리포트를 출력합니다.

    웹페이지(index.html)에서 보여주는 것과 동일한 정보를 텍스트로 표시하여,
    파이썬 스크립트 단독 실행만으로도 결과를 확인할 수 있도록 합니다.
    """
    line = "─" * 56
    print()
    print("╔" + "═" * 56 + "╗")
    print(f"║  {result['school']:<52}  ║")
    print(f"║  {'캠퍼스 시간대별 산책지수':<48}  ║")
    print("╚" + "═" * 56 + "╝")
    print()

    # 대기 정보
    air = result["air"]
    print("◆ 대기 상태")
    if air["pm10"] >= 0:
        print(f"   PM10  {int(air['pm10']):>3} ㎍/㎥   PM2.5 {int(air['pm25']):>3} ㎍/㎥   →  {air['label']}")
    else:
        print(f"   미세먼지 측정값 없음  ({air['station']})")
    print(f"   측정소  {air.get('station', '-')}    측정시각 {air.get('measured_at', '-')}")
    print(f"   업데이트 {result['generated_at']}")
    print()

    # 황금시간
    bt = result.get("best_time")
    if bt:
        print("◆ 오늘 산책 황금시간")
        print(f"   ★ {bt['hour']:>2}시  점수 {bt['score']}")
        print(f"     {bt['sky_text']} · {bt['tmp']:.0f}℃ · 강수확률 {int(bt['pop'])}% · 풍속 {bt['wsd']}m/s")
        print()

    # 시간대별 막대 그래프
    print("◆ 시간대별 점수")
    print(f"   {'시각':<5} {'점수':<5} {'그래프 (●=10점)':<22} {'기상'}")
    print("   " + line)
    for h in result["hourly"]:
        bar_len = int(h["score"] / 5)  # 100점 = 20칸
        bar = "█" * bar_len
        print(
            f"   {h['hour']:>2}시  {int(h['score']):>3}   "
            f"{bar:<22} "
            f"{h['sky_text']} {h['tmp']:.0f}℃ "
            f"({h['note']})"
        )
    print()

    # 추천 코스
    if routes_data:
        score = bt["score"] if bt else 0
        print(f"◆ 추천 코스  (현재 점수 {score} 기준)")
        for r in routes_data.get("routes", []):
            recommended = score >= r.get("min_score", 0)
            mark = "✓ 추천" if recommended else "  -- "
            print(
                f"   [{mark}] {r['name']:<6} "
                f"{r['duration_min']:>2}분  {r['distance_km']:>4}km  "
                f"· {r['subtitle']}"
            )
        print()
        print("   ※ 사용자가 그린 '내 코스'는 웹페이지에서 추가/관리합니다.")
        print()

    # 친구 톤 메시지
    if bt:
        s = bt["score"]
        if s >= 80:
            msg = "오늘 진짜 산책각이야. 친구 불러봐"
        elif s >= 60:
            msg = "괜찮은 정도. 잠깐 바람 쐬기엔 OK"
        elif s >= 40:
            msg = "굳이? 안 나가도 되는 날인 듯"
        else:
            msg = "오늘은 매점 ㄱㄱ. 산책은 패스하자"
        print(f"◆ 한마디  ─  \"{msg}\"")
        print()

    # 출처
    print("◆ 데이터 출처 (공공데이터포털)")
    print("   · 기상청_단기예보 조회서비스")
    print("   · 한국환경공단_에어코리아_대기오염정보")
    print("   · 지도 타일: OpenStreetMap contributors")
    print()


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    env = load_env(base_dir / ".env")
    service_key = env.get("SERVICE_KEY") or os.environ.get("SERVICE_KEY", "")
    if not service_key or "여기에" in service_key:
        print("[ERROR] .env 파일에 SERVICE_KEY 가 설정되어 있지 않습니다.", file=sys.stderr)
        print("        .env.example 을 참고해 .env 파일을 만들어 주세요.", file=sys.stderr)
        return 1

    nx, ny = latlon_to_grid(SCHOOL_LAT, SCHOOL_LON)
    print(f"[INFO] {SCHOOL_NAME} 격자좌표: nx={nx}, ny={ny}")

    print("[INFO] 기상청 단기예보 호출 중...")
    weather = fetch_weather(service_key, nx, ny)
    print(f"[INFO] 예보 시간 {len(weather)}건 수집")

    print("[INFO] 에어코리아 대기오염정보 호출 중...")
    try:
        air = fetch_air(service_key)
        print(f"[INFO] 측정소: {air.get('station')}, PM10={air['pm10']}, PM2.5={air['pm25']}")
    except Exception as e:
        print(f"[WARN] 에어코리아 호출 실패 ({e}).")
        print("       data.go.kr 마이페이지에서 '한국환경공단_에어코리아_대기오염정보' 활용신청을 추가로 해주세요.")
        print("       당장은 미세먼지 정보 없이 기상 점수만 반영합니다.")
        air = {"pm10": -1, "pm25": -1, "station": "활용신청 대기 중", "measured_at": ""}

    result = build_recommendations(weather, air)

    out = base_dir / "data.json"
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {out.name} 생성 완료 ({len(result['hourly'])} 시간대)")

    # routes.json 도 함께 읽어 콘솔 리포트 출력
    routes_path = base_dir / "routes.json"
    routes_data: dict[str, Any] | None = None
    if routes_path.exists():
        try:
            routes_data = json.loads(routes_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] routes.json 읽기 실패: {e}")
    print_report(result, routes_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
