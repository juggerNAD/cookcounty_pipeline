import os
import re
import csv
import json
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageEnhance, ImageOps

PDF_DIR = "pdf"
PHASE3_CSV = "phase3_results.csv"
PHASE3_JSON = "phase3_results.json"

# =========================
# OCR — SCANNED PDF SAFE
# =========================
def ocr_pdf(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
        full_text = ""

        for img in images:
            t1 = pytesseract.image_to_string(img, config="--oem 3 --psm 6")

            gray = img.convert("L")
            contrast = ImageEnhance.Contrast(gray).enhance(3.0)
            sharp = ImageEnhance.Sharpness(contrast).enhance(2.0)
            t2 = pytesseract.image_to_string(sharp, config="--oem 3 --psm 6")

            inverted = ImageOps.invert(contrast)
            t3 = pytesseract.image_to_string(inverted, config="--oem 3 --psm 6")

            full_text += "\n".join([t1, t2, t3]) + "\n"

        text = full_text.upper()
        text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    except Exception as e:
        print(f"❌ OCR failed on {pdf_path}: {e}")
        return ""

# =========================
# CASE NUMBER — NO LETTER ASSUMPTIONS
# =========================
def extract_case_number(text):
    pattern = re.compile(
        r"\b(20\d{2}|\d{2})[\s\-]*[A-Z]{1,10}[\s\-]*\d{2,8}\b"
    )

    candidates = []
    for m in pattern.finditer(text):
        raw = m.group()
        cleaned = re.sub(r"[\s\-]+", "", raw)

        if not re.search(r"\d{2,8}$", cleaned):
            continue

        candidates.append(cleaned)

    if not candidates:
        return "", 0.0

    best = max(candidates, key=len)
    return best, 0.95

# =========================
# AMOUNT — FIXED (NO INDEX ERROR)
# =========================
def extract_amount(text):
    patterns = [
        r"(?:AMOUNT CLAIMED|CLAIMED AMOUNT|TOTAL AMOUNT)[^$0-9]{0,40}(\$?\s?[\d,]+\.\d{2})",
        r"(\$[\d,]+\.\d{2})"
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = m.group(1)
            val = val.replace("$", "").replace(",", "")
            return f"${float(val):,.2f}", 0.9

    return "", 0.0

# =========================
# ADDRESS — US FORMAT
# =========================
def extract_address(text):
    addr_pattern = re.compile(
        r"\b\d{1,6}\s+[A-Z0-9 .,'\-]+?\s+"
        r"(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|CT|COURT|BLVD|LN|WAY)\b"
        r".{0,40}?\b[A-Z]{2}\s*\d{5}\b"
    )

    m = addr_pattern.search(text)
    if m:
        return m.group(0).strip(), 0.9

    return "", 0.0

# =========================
# PROCESS SINGLE PDF
# =========================
def process_pdf(pdf_file):
    text = ocr_pdf(os.path.join(PDF_DIR, pdf_file))

    case, c_conf = extract_case_number(text)
    amt, a_conf = extract_amount(text)
    addr, ad_conf = extract_address(text)

    return {
        "Source PDF": pdf_file,
        "Case Number": case,
        "Case Confidence": c_conf,
        "Amount (USD)": amt,
        "Amount Confidence": a_conf,
        "Address": addr,
        "Address Confidence": ad_conf
    }

# =========================
# LOAD CSV STATE (RESUME)
# =========================
def load_csv_state():
    completed = set()
    if not os.path.exists(PHASE3_CSV):
        return completed

    with open(PHASE3_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            completed.add(row["Source PDF"])

    return completed

# =========================
# SAVE RESULT (UPSERT)
# =========================
def save_result(result):
    rows = []

    if os.path.exists(PHASE3_CSV):
        with open(PHASE3_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    rows = [r for r in rows if r["Source PDF"] != result["Source PDF"]]
    rows.append(result)

    with open(PHASE3_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        writer.writeheader()
        writer.writerows(rows)

    with open(PHASE3_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=4)

# =========================
# MAIN LOOP
# =========================
def process_all_pdfs():
    completed = load_csv_state()

    for pdf in sorted(os.listdir(PDF_DIR)):
        if not pdf.lower().endswith(".pdf"):
            continue
        if pdf in completed:
            continue

        print(f"Processing {pdf}...")
        result = process_pdf(pdf)
        save_result(result)
        print(f"✅ Done: {result['Case Number']}\n")

if __name__ == "__main__":
    process_all_pdfs()
    print("🎯 PHASE 3 COMPLETE")
