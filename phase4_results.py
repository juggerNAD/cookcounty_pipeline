import asyncio
import csv
import json
import random
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError

# =========================
# CONFIG
# =========================

PHASE3_CSV = "phase3_results.csv"
OUTPUT_CSV = "phase4_results.csv"
OUTPUT_JSON = "phase4_results.json"

SEARCH_URL = "https://casesearch.cookcountyclerkofcourt.org/CivilCaseSearchAPI.aspx"

BATCH_SIZE = 5
SHORT_DELAY = (4, 8)        # between individual cases
LONG_DELAY = (30, 90)      # after every 5 cases

# =========================
# USER AGENTS
# =========================

USER_AGENTS = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",

    # Brave
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/1.62",

    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",

    # Mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",

    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
]

# =========================
# VIEWPORT ROTATION
# =========================

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 390, "height": 844},   # iPhone
    {"width": 412, "height": 915},   # Android
]

# =========================
# EXCLUSION EVENTS
# =========================

EXCLUDE_EVENTS = [
    "Certificate of Sale",
    "Receipt of Sale",
    "Report of Sale",
    "Sheriff’s Sale Approved",
    "Mortgage Foreclosure Disposed",
    "Dismissed",
    "Voluntary Dismissal",
    "Sale Vacated",
    "Order for Possession",
    "Eviction",
]

# =========================
# FILE INITIALIZATION
# =========================

def init_files():
    if not Path(OUTPUT_CSV).exists():
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Case Number", "Address", "Status", "Color Tag"])

    if not Path(OUTPUT_JSON).exists():
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def save_result(row):
    # CSV (real-time)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

    # JSON (real-time)
    with open(OUTPUT_JSON, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append({
            "Case Number": row[0],
            "Address": row[1],
            "Status": row[2],
            "Color Tag": row[3],
        })
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()


# =========================
# SCRAPE SINGLE CASE
# =========================

async def check_case(page, case_number):
    await page.goto(SEARCH_URL, timeout=60000)

    await page.fill("#MainContent_txtCaseNumber", case_number)
    await page.click("#MainContent_btnSearch")

    await page.wait_for_load_state("networkidle")

    text = await page.inner_text("body")

    if "Judgment of Foreclosure" in text:
        return "Judgment of Foreclosure", "GREEN"

    for event in EXCLUDE_EVENTS:
        if event in text:
            return event, "RED"

    return "No Judgment Found", "NEUTRAL"


# =========================
# MAIN RUNNER
# =========================

async def run_phase4():
    init_files()

    df = pd.read_csv(PHASE3_CSV)
    cases = df.dropna(subset=["Case Number"]).to_dict("records")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for batch_index in range(0, len(cases), BATCH_SIZE):
            batch = cases[batch_index: batch_index + BATCH_SIZE]

            print(f"\n🔵 Batch {(batch_index // BATCH_SIZE) + 1}")

            for i, row in enumerate(batch, start=1):
                case_number = str(row["Case Number"]).strip()
                address = row.get("Address", "")

                print(f"[{batch_index + i}] Checking case {case_number}")

                viewport = random.choice(VIEWPORTS)

                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport=viewport
                )

                page = await context.new_page()

                try:
                    status, color = await check_case(page, case_number)
                    save_result([case_number, address, status, color])
                except TimeoutError:
                    print(f"❌ Timeout: {case_number}")
                except Exception as e:
                    print(f"❌ Failed {case_number}: {e}")
                finally:
                    await context.close()
                    time.sleep(random.uniform(*SHORT_DELAY))

            print("⏸ Pausing before next batch...")
            time.sleep(random.uniform(*LONG_DELAY))

        await browser.close()


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    asyncio.run(run_phase4())