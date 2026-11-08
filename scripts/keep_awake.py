"""Open the live Streamlit app in a headless browser and wake it if Streamlit Community Cloud put it to sleep.

Free Community Cloud apps sleep after about 12 hours without visitors. The keep-awake GitHub Action runs this
every few hours, so the app always has a recent visit and the first real visitor never waits for a cold boot.
"""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://team24-logisticslanedealroom.streamlit.app/")
READY_TEXT = "Convene committee"
WAKE_BUTTON = "Yes, get this app back up!"


def main() -> int:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=120_000)
        woke = False
        deadline = time.time() + 600
        while time.time() < deadline:
            btn = page.get_by_role("button", name=WAKE_BUTTON)
            if btn.count():
                print(f"{time.time() - t0:5.1f}s app was asleep, clicking the wake button")
                btn.first.click()
                woke = True
            if any(f.get_by_text(READY_TEXT).count() for f in page.frames):
                print(f"{time.time() - t0:5.1f}s app is up (woke={woke})")
                browser.close()
                return 0
            time.sleep(3)
        print("app did not become ready within 10 minutes")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
