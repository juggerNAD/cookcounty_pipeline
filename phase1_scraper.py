from playwright.sync_api import sync_playwright
import csv
import json
import os
import calendar
from datetime import datetime

# ======================
# SAFE PRINT
# ======================
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "ignore").decode())


# ======================
# CONFIG
# ======================
BASE_URL = "https://crs.cookcountyclerkil.gov"
SEARCH_URL = f"{BASE_URL}/Search"

CSV_FILE = "phase1_results.csv"
JSON_FILE = "phase1_results.json"


# ======================
# LOAD EXISTING DOCS
# ======================
def load_existing_docs():
    seen = set()

    # Load from CSV
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for r in reader:
                if len(r) > 2:
                    seen.add(r[2])

    # Load from JSON
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                if "Document Number" in item:
                    seen.add(item["Document Number"])

    safe_print(f"[INFO] Loaded {len(seen)} existing document numbers from CSV/JSON")
    return seen


# ======================
# DATE RANGE (AUTO)
# ======================
def get_month_dates(year, month):
    today = datetime.today()
    from_date = datetime(year, month, 1)

    if year == today.year and month == today.month:
        to_date = today
    else:
        last_day = calendar.monthrange(year, month)[1]
        to_date = datetime(year, month, last_day)

    return (
        from_date.strftime("%m/%d/%Y"),
        to_date.strftime("%m/%d/%Y")
    )


# ======================
# PHASE 1 CORE (STOP ON ANY DUPLICATE)
# ======================
def run_phase1(from_date, to_date, seen_docs):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(SEARCH_URL)

        page.click("text=Advanced Search")
        page.wait_for_timeout(1000)

        accordion = page.query_selector(
            "button.accordion-button:has-text('Document Type Search')"
        )
        accordion.scroll_into_view_if_needed()
        accordion.click()

        page.wait_for_selector("div#collapse3.accordion-collapse.show")

        page.select_option(
            "div#collapse3 select#DocumentType",
            label="LIS PENDENS FORECLOSURE"
        )

        # Fill date range
        page.fill("div#collapse3 input#RecordedFromDate", from_date)
        page.fill("div#collapse3 input#RecordedToDate", to_date)

        page.click("div#collapse3 button[type='submit']")
        page.wait_for_selector("table tbody tr", timeout=30000)

        while True:
            rows = page.query_selector_all("table tbody tr")

            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) < 3:
                    continue

                doc_number = cells[2].inner_text().strip()

                # ❌ Stop immediately if duplicate found
                if doc_number in seen_docs:
                    safe_print(f"[STOP] Document already exists: {doc_number}")
                    browser.close()
                    return False

                # Collect row data
                row_data = []
                for i, cell in enumerate(cells):
                    if i == 1:
                        link = cell.query_selector("a")
                        href = link.get_attribute("href") if link else ""
                        row_data.append(BASE_URL + href if href else "")
                    else:
                        row_data.append(cell.inner_text().strip())

                # Write immediately to CSV
                file_exists = os.path.exists(CSV_FILE)
                with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow([
                            "Empty", "View URL", "Document Number", "Recorded Date",
                            "Filed Date", "Document Type", "Empty2",
                            "Company", "Name", "Phone", "Parcel/Address"
                        ])
                    writer.writerow(row_data)

                # Update seen_docs to prevent re-processing within the same run
                seen_docs.add(doc_number)

            # Pagination
            next_btn = page.query_selector("li.PagedList-skipToNext a[rel='next']")
            if next_btn:
                next_btn.click()
                page.wait_for_timeout(2000)
            else:
                break

        browser.close()

    safe_print(f"[OK] Month {from_date} → {to_date} scraped successfully")
    return True


# ======================
# AUTO MONTH LOOP
# ======================
def run_auto():
    seen_docs = load_existing_docs()
    current = datetime.today().replace(day=1)
    stop_date = datetime(2024, 1, 1)

    while current >= stop_date:
        from_date, to_date = get_month_dates(current.year, current.month)
        safe_print(f"[INFO] Scraping {from_date} → {to_date}")

        cont = run_phase1(from_date, to_date, seen_docs)
        if cont is False:
            safe_print("[STOP] Scraper halted completely due to duplicate document")
            break

        # Move to previous month
        if current.month == 1:
            current = current.replace(year=current.year - 1, month=12)
        else:
            current = current.replace(month=current.month - 1)


# ======================
# ENTRY POINT
# ======================
if __name__ == "__main__":
    run_auto()
