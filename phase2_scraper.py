from playwright.sync_api import sync_playwright
import csv
import json
import os
import time
import requests

BASE_URL = "https://crs.cookcountyclerkil.gov"

PHASE1_CSV = "phase1_results.csv"
PHASE2_CSV = "phase2_results.csv"
PHASE2_JSON = "phase2_results.json"

PDF_DIR = "pdf"
os.makedirs(PDF_DIR, exist_ok=True)

MAX_PDF_RETRIES = 3
PDF_MIN_SIZE = 10_000  # bytes


# =========================
# CLOUDFLARE HUMAN CHECK
# =========================
def wait_for_cloudflare(page, timeout=120):
    print("⏳ Checking for Cloudflare...")
    start = time.time()

    while time.time() - start < timeout:
        html = page.content().lower()
        if "cloudflare" in html or "checking your browser" in html or "cf-turnstile" in html:
            print("🛑 Cloudflare detected. Please solve it in the browser...")
            time.sleep(2)
        else:
            print("✅ Cloudflare cleared.")
            return

    raise Exception("Cloudflare not cleared")


# =========================
# LOAD PHASE 1
# =========================
def load_phase1():
    with open(PHASE1_CSV, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("View URL")]


# =========================
# LOAD COMPLETED DOCS (CSV + PDF)
# =========================
def load_completed_docs():
    done = set()
    if not os.path.exists(PHASE2_CSV):
        return done

    with open(PHASE2_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pdf_path = r.get("PDF Path", "")
            if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) >= PDF_MIN_SIZE:
                done.add(r["Document Number"])
    return done


# =========================
# PDF DOWNLOAD WITH RETRY
# =========================
def download_pdf(pdf_url, pdf_path):
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) >= PDF_MIN_SIZE:
        return True

    for attempt in range(1, MAX_PDF_RETRIES + 1):
        try:
            print(f"⬇️ Downloading PDF (attempt {attempt})")
            r = requests.get(pdf_url, timeout=60)

            if r.status_code == 429:
                raise Exception("429 Too Many Requests")

            r.raise_for_status()

            tmp = pdf_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(r.content)

            if os.path.getsize(tmp) < PDF_MIN_SIZE:
                raise Exception("PDF too small")

            os.replace(tmp, pdf_path)
            return True

        except Exception as e:
            print(f"⚠ PDF download failed: {e}")
            time.sleep(5 * attempt)

    return False


# =========================
# SCRAPE SINGLE VIEW PAGE
# =========================
def scrape_view(page, record):
    page.goto(record["View URL"], timeout=60000)
    wait_for_cloudflare(page)

    page.wait_for_selector("#divcol1 table tbody tr", timeout=30000)

    def safe_text(selector):
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else ""

    doc_number = safe_text("#divcol1 table tbody tr:nth-child(1) td")
    doc_type = safe_text("#divcol1 table tbody tr:nth-child(2) td")
    date_recorded = safe_text("#divcol1 table tbody tr:nth-child(3) td")
    address = safe_text("#divcol1 table tbody tr:nth-child(6) td span")

    iframe = page.query_selector("iframe#iframe")
    pdf_path = ""

    if iframe:
        src = iframe.get_attribute("src")
        if src:
            pdf_url = BASE_URL + src
            pdf_path = os.path.join(PDF_DIR, f"{doc_number}.pdf")

            if not download_pdf(pdf_url, pdf_path):
                raise Exception("PDF failed after retries")

    return {
        "Document Number": doc_number,
        "Document Type": doc_type,
        "Date Recorded": date_recorded,
        "Address": address,
        "View URL": record["View URL"],
        "PDF Path": pdf_path
    }


# =========================
# MAIN PHASE 2 (AUTO RESUME)
# =========================
def run_phase2():
    phase1_records = load_phase1()
    completed_docs = load_completed_docs()

    results = []
    if os.path.exists(PHASE2_JSON):
        with open(PHASE2_JSON, encoding="utf-8") as f:
            results = json.load(f)

    while True:  # 🔁 AUTO-RESUME LOOP
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, slow_mo=80)
                context = browser.new_context()
                pages = [context.new_page() for _ in range(3)]

                for i in range(0, len(phase1_records), 3):
                    batch = phase1_records[i:i + 3]

                    jobs = [
                        (page, record)
                        for page, record in zip(pages, batch)
                        if record["Document Number"] not in completed_docs
                    ]

                    for page, record in jobs:
                        try:
                            data = scrape_view(page, record)

                            completed_docs.add(data["Document Number"])
                            results.append(data)

                            file_exists = os.path.exists(PHASE2_CSV)
                            with open(PHASE2_CSV, "a", newline="", encoding="utf-8") as f:
                                writer = csv.DictWriter(f, fieldnames=data.keys())
                                if not file_exists:
                                    writer.writeheader()
                                writer.writerow(data)

                            with open(PHASE2_JSON, "w", encoding="utf-8") as f:
                                json.dump(results, f, indent=4)

                            print(f"✅ Scraped: {data['Document Number']}")

                        except Exception as e:
                            print(f"❌ Record failed, will retry later: {e}")

                        time.sleep(1.5)

                browser.close()
                print("🎉 All records processed")
                return

        except Exception as e:
            print(f"🔥 Browser crashed: {e}")
            print("🔁 Restarting browser in 30 seconds...")
            time.sleep(30)


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    run_phase2()
