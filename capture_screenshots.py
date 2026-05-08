"""
스크린샷 자동 캡처
================================================
실행하면 다음 4개의 PNG 가 screenshots/ 폴더에 자동 생성됩니다.
이후 build_report.py 를 실행하면 PDF 보고서에 자동 삽입됩니다.

  - screenshots/main.png    : 웹 페이지 전체
  - screenshots/map.png     : 위성 지도 + 코스
  - screenshots/hourly.png  : 시간대별 그리드
  - screenshots/app.png     : 파이썬 GUI (tkinter)

요구사항:
  py -m pip install selenium pillow

실행:
  py capture_screenshots.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


BASE = Path(__file__).resolve().parent
SHOTS = BASE / "screenshots"
SHOTS.mkdir(exist_ok=True)

PORT = 8766
URL = f"http://localhost:{PORT}"


def capture_web() -> None:
    """헤드리스 Edge 로 웹 페이지 3컷 캡처."""
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
    except ImportError:
        print(
            "[ERR] selenium 미설치. 다음 명령으로 설치하세요:\n"
            "      py -m pip install selenium pillow",
            file=sys.stderr,
        )
        sys.exit(1)

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=str(BASE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1)

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,1700")

        driver = webdriver.Edge(options=opts)
        try:
            driver.set_window_size(1280, 1700)
            driver.get(URL)
            # 데이터 fetch + Leaflet 타일 다운로드 + 폰트 로드 대기
            time.sleep(5)

            # 메인 화면 (전체 페이지 스크롤 포함)
            driver.save_screenshot(str(SHOTS / "main.png"))
            print(f"[OK] {SHOTS / 'main.png'}")

            # 지도 영역만
            try:
                map_el = driver.find_element("id", "map")
                map_el.screenshot(str(SHOTS / "map.png"))
                print(f"[OK] {SHOTS / 'map.png'}")
            except Exception as e:
                print(f"[WARN] map.png 생성 실패: {e}")

            # 시간대별 그리드 영역
            try:
                hourly_el = driver.find_element("id", "hourlySection")
                hourly_el.screenshot(str(SHOTS / "hourly.png"))
                print(f"[OK] {SHOTS / 'hourly.png'}")
            except Exception as e:
                print(f"[WARN] hourly.png 생성 실패: {e}")
        finally:
            driver.quit()
    finally:
        server.terminate()


def capture_app() -> None:
    """app.py 를 --capture 모드로 실행 → 자체 캡처 후 종료."""
    try:
        result = subprocess.run(
            [sys.executable, str(BASE / "app.py"), "--capture"],
            cwd=str(BASE),
            timeout=20,
        )
        if result.returncode == 0:
            print(f"[OK] {SHOTS / 'app.png'}")
        else:
            print(f"[WARN] app.png 캡처 종료코드 {result.returncode}")
    except subprocess.TimeoutExpired:
        print("[WARN] app.py 캡처 시간 초과")
    except Exception as e:
        print(f"[ERR] app 캡처 실패: {e}")


def main() -> int:
    print("[1/2] 웹 페이지 캡처 (헤드리스 Edge)...")
    capture_web()
    print()
    print("[2/2] 데스크톱 GUI 캡처 (tkinter)...")
    capture_app()
    print()
    print("[DONE] screenshots/ 폴더 확인 후 'py build_report.py' 실행하면")
    print("       PDF 보고서에 자동 삽입됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
