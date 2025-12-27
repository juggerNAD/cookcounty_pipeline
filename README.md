Cook County Document Pipeline

🚀 Overview



The Cook County Document Pipeline is a fully automated, multi-phase scraping and data processing system designed to collect, process, and enrich public records from Cook County websites.



This pipeline is state-aware, idempotent, and safe to run daily.

It automatically detects previously processed records and exits early when no new data is available.



Once configured, the pipeline can run unattended on macOS using system scheduling.



🧠 Key Features



✅ Multi-phase execution (Phase 1 → Phase 4)



✅ Automatic continuation between phases



✅ Duplicate detection across CSV, JSON, and filesystem



✅ PDF downloading and OCR extraction



✅ Case status enrichment via court search



✅ Centralized Excel output (multiple sheets)



✅ Incremental saving (crash-safe)



✅ Daily automation support (launchd)



✅ No manual intervention required after setup



🧩 Pipeline Architecture



Phase 1 → Phase 2 → Phase 3 → Phase 4

&nbsp;  │         │         │         │

&nbsp;  ▼         ▼         ▼         ▼

&nbsp;CSV/JSON  PDFs     OCR Data   Case Status



Each phase only runs if necessary.

If all data has already been processed, the pipeline exits automatically.



🔄 Phase Breakdown

Phase 1 — Document Index Scraper



File: phase1\_scraper.py



Scrapes Cook County document listings by date range



Saves:



phase1\_results.csv



phase1\_results.json



Detects previously scraped document numbers



Stops automatically when no new records exist



Phase 2 — Document Detail Scraper \& PDF Downloader



File: phase2\_scraper.py



Loads results from Phase 1



Scrapes document detail pages



Downloads associated PDFs



Saves:



phase2\_results.csv



phase2\_results.json



PDFs into /pdf directory



Skips documents already processed



Phase 3 — OCR \& Data Extraction



File: phase3\_results.py



Performs OCR on downloaded PDFs



Extracts:



Case numbers



Dollar amounts



Property addresses



Uses multi-pass OCR for watermark-heavy documents



Saves:



phase3\_results.csv



phase3\_results.json



Prevents duplicate case processing



Phase 4 — Case Status Enrichment



File: phase4\_results.py



Searches Cook County court records by case number



Determines foreclosure or dismissal status



Assigns color-coded tags



Saves:



phase4\_results.csv



phase4\_results.json



Includes:



User-agent rotation



Viewport randomization



Rate limiting



🧠 Central Orchestration

run\_pipeline.py



This is the single entry point for the entire system



python run\_pipeline.py



What it does:



Runs Phase 1 until completion or early exit



Automatically triggers Phase 2



Then Phase 3



Then Phase 4



Consolidates results into a single Excel file:



centralized\_results.xlsx



One sheet per phase



You never run individual phases manually in production.



📊 Output Files



Generated automatically on first run:



phase1\_results.csv / .json

phase2\_results.csv / .json

phase3\_results.csv / .json

phase4\_results.csv / .json

centralized\_results.xlsx

pdf/



All files are saved in the project root directory.



🖥️ System Requirements

macOS (Recommended)



Python 3.10+

Playwright

Tesseract OCR

Poppler (PDF rendering)

Required System Tools



brew install python

brew install tesseract

brew install poppler



📦 Python Dependencies



Installed automatically via pip:



playwright

pandas

openpyxl

pytesseract

pdf2image

pillow

requests



⚙️ Setup Instructions (macOS)



git clone https://github.com/YOUR\_USERNAME/cook-county-document-pipeline.git

cd cook-county-document-pipeline



python3 -m venv venv

source venv/bin/activate



pip install -r requirements.txt

playwright install



python run\_pipeline.py



⏱️ Daily Automation (macOS)



This pipeline is designed to be safely run once per day using launchd.



Automatically exits if no new data exists

Safe to run unattended

Logs output to file

(See /docs/automation.md if included)



🛑 Important Notes



This project scrapes publicly accessible records

Cloudflare human verification may require manual intervention

Designed for research and data analysis purposes

Respect website terms of service



🧪 Development Notes



Each phase is intentionally independent

CSV + JSON outputs are written incrementally

The pipeline is crash-resilient by design

Safe to stop and restart at any point



📄 License



MIT License (recommended)



👤 Author



Built by \[Your Name]



Automation-focused, state-aware scraping pipeline for structured public records.

