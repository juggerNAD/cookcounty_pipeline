from playwright.sync_api import sync_playwright
import csv
import json
import os
import time
import requests

BASE_URL = "https://crs.cookcountyclerkil.gov"

PHASE1_CSV = "phase1_results.csv"
PHASE1_JSON = "phase1_results.json"

PHASE2_CSV = "phase2_results.csv"
PHASE2_JSON = "phase2_results.json"

PDF_DIR = "pdf"
os.makedirs(PDF_DIR, exist_ok=True)


# =========================
# CLOUDFLARE HUMAN CHECK
# =========================
def wait_for_cloudflare(page, timeout=120):
    """
    Pauses execution until Cloudflare challenge
    is manually solved by a human.
    """
    print("⏳ Checking for Cloudflare...")

    start = time.time()
    while time.time() - start < timeout:
        html = page.content().lower()

        if (
            "checking your browser" in html
            or "cf-turnstile" in html
            or "cloudflare" in html
        ):
            print("🛑 Cloudflare detected. Please solve it in the browser...")
            time.sleep(2)
        else:
            print("✅ Cloudflare cleared.")
            return

    print("⚠ Cloudflare wait timeout reached. Continuing...")


# =========================
# LOAD PHASE 1 VIEW URLS
# =========================
def load_phase1():
    records = []
    with open(PHASE1_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("View URL"):
                records.append(row)
    return records


# =========================
# LOAD COMPLETED DOCS
# =========================
def load_completed_docs():
    done = set()
    if os.path.exists(PHASE2_CSV):
        with open(PHASE2_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                done.add(r["Document Number"])
    return done


# =========================
# SCRAPE SINGLE VIEW PAGE
# =========================
def scrape_view(page, record):
    page.goto(record["View URL"], timeout=60000)

    # 🔐 WAIT FOR HUMAN TO PASS CLOUDFLARE
    wait_for_cloudflare(page)

    page.wait_for_selector("#divcol1 table tbody tr", timeout=30000)

    def safe_text(selector):
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else ""

    doc_number = safe_text("#divcol1 > div.table-responsive > table > tbody > tr:nth-child(1) > td")
    doc_type = safe_text("#divcol1 > div.table-responsive > table > tbody > tr:nth-child(2) > td")
    date_recorded = safe_text("#divcol1 > div.table-responsive > table > tbody > tr:nth-child(3) > td")
    address = safe_text("#divcol1 > div.table-responsive > table > tbody > tr:nth-child(6) > td > span")

    # =========================
    # PDF DOWNLOAD
    # =========================
    iframe = page.query_selector("iframe#iframe")
    pdf_path = ""

    if iframe:
        src = iframe.get_attribute("src")
        if src:
            pdf_url = BASE_URL + src
            pdf_path = os.path.join(PDF_DIR, f"{doc_number}.pdf")

            if not os.path.exists(pdf_path):
                r = requests.get(pdf_url)
                with open(pdf_path, "wb") as f:
                    f.write(r.content)

    return {
        "Document Number": doc_number,
        "Document Type": doc_type,
        "Date Recorded": date_recorded,
        "Address": address,
        "View URL": record["View URL"],
        "PDF Path": pdf_path
    }


# =========================
# MAIN PHASE 2
# =========================
def run_phase2():
    phase1_records = load_phase1()
    completed_docs = load_completed_docs()

    results = []
    if os.path.exists(PHASE2_JSON):
        with open(PHASE2_JSON, encoding="utf-8") as f:
            results = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,   # 👀 ALWAYS VISIBLE
            slow_mo=80        # 🧠 HUMAN-LIKE SPEED
        )

        context = browser.new_context()
        pages = [context.new_page() for _ in range(3)]

        for i in range(0, len(phase1_records), 3):
            batch = phase1_records[i:i + 3]

            jobs = []
            for page, record in zip(pages, batch):
                if record["Document Number"] in completed_docs:
                    continue
                jobs.append((page, record))

            for page, record in jobs:
                try:
                    data = scrape_view(page, record)

                    if not data["Document Number"]:
                        continue

                    results.append(data)
                    completed_docs.add(data["Document Number"])

                    file_exists = os.path.exists(PHASE2_CSV)
                    with open(PHASE2_CSV, "a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=data.keys())
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow(data)

                    with open(PHASE2_JSON, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=4)

                    print(f"✅ Phase 2 scraped: {data['Document Number']}")

                except Exception as e:
                    print(f"❌ Error on {record['View URL']}: {e}")

                time.sleep(1.5)  # 🧍 Human pacing

        browser.close()


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    run_phase2()