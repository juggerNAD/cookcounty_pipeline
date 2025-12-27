import os
import re
import json
import csv
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageEnhance, ImageOps

PDF_DIR = "pdf"
PHASE3_CSV = "phase3_results.csv"
PHASE3_JSON = "phase3_results.json"


# =========================
# WATERMARK-BOOSTED OCR
# =========================
def ocr_pdf(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
        full_text = ""

        tesseract_config = r"--oem 3 --psm 6"

        for img in images:
            # Pass 1: Normal OCR
            text1 = pytesseract.image_to_string(img, config=tesseract_config)

            # Pass 2: Watermark boost
            gray = img.convert("L")
            contrast = ImageEnhance.Contrast(gray).enhance(3.0)
            inverted = ImageOps.invert(contrast)
            text2 = pytesseract.image_to_string(inverted, config=tesseract_config)

            full_text += text1 + "\n" + text2 + "\n"

        # Normalize watermark spacing damage
        full_text = full_text.upper()
        full_text = re.sub(r"(\d)\s+(\d)", r"\1\2", full_text)
        full_text = re.sub(r"C\s*H", "CH", full_text)
        full_text = re.sub(r"F\s*C", "FC", full_text)
        full_text = re.sub(r"\s+", " ", full_text)

        return full_text.strip()

    except Exception as e:
        print(f"❌ OCR failed for {pdf_path}: {e}")
        return ""


# =========================
# CASE NUMBER (ROBUST)
# =========================
def extract_case_number(text):
    patterns = [
        r"\b\d{4}CH\d{3,6}\b",
        r"\b\d{4}\s*CH\s*\d{3,6}\b",
        r"\b\d{2}\s*CH\s*\d{3,6}\b",
        r"\b\d{4}-CH-\d{3,6}\b",
        r"\b\d{4}L\d{3,6}\b",
        r"\b\d{4}\s*L\s*\d{3,6}\b",
        r"\b\d{4}FC\d{3,6}\b",
        r"\b\d{4}-M6-\d{3,6}\b",
        r"\b\d{4}\s*P\s*\d{3,6}\b",
        r"\b\d{2}\s*ED\s*\d{3,6}\b",
    ]

    matches = []
    for pat in patterns:
        found = re.findall(pat, text, re.IGNORECASE)
        for f in found:
            cleaned = re.sub(r"\s+", "", f.upper())
            matches.append(cleaned)

    if not matches:
        return "", 0.0

    # Choose the longest / most complete case
    best = max(matches, key=len)
    return best, 0.95


# =========================
# AMOUNT (NO DUPLICATION)
# =========================
def extract_amount(text):
    matches = re.findall(r"\$\s?[\d,]+\.\d{2}", text)
    if not matches:
        return "", 0.0

    values = []
    for m in matches:
        try:
            values.append(float(m.replace("$", "").replace(",", "")))
        except:
            pass

    if not values:
        return "", 0.0

    return f"${max(values):,.2f}", 0.9


# =========================
# ADDRESS (STRICT)
# =========================
def extract_address(text):
    # Full address pattern: street + city + state + zip
    match = re.search(
        r"\d{1,5}\s+[\w\s.#-]+,\s*[A-Z]{2}\s*\d{5}",
        text
    )
    if match:
        return match.group(0).strip(), 0.9

    return "", 0.0


# =========================
# PROCESS PDF
# =========================
def process_pdf(pdf_file, seen_cases):
    pdf_path = os.path.join(PDF_DIR, pdf_file)
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return None

    text = ocr_pdf(pdf_path)

    case_number, case_conf = extract_case_number(text)
    amount, amount_conf = extract_amount(text)
    address, addr_conf = extract_address(text)

    if case_number and case_number in seen_cases:
        print(f"⚠ Duplicate case skipped: {case_number}")
        return None

    return {
        "Source PDF": pdf_file,
        "Case Number": case_number,
        "Case Confidence": case_conf,
        "Amount (USD)": amount,
        "Amount Confidence": amount_conf,
        "Address": address,
        "Address Confidence": addr_conf
    }


# =========================
# SAVE RESULTS
# =========================
def save_result(result):
    data = []
    if os.path.exists(PHASE3_JSON):
        with open(PHASE3_JSON, encoding="utf-8") as f:
            data = json.load(f)

    data.append(result)

    with open(PHASE3_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    write_header = not os.path.exists(PHASE3_CSV)
    with open(PHASE3_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(result)


# =========================
# BATCH PROCESS
# =========================
def process_all_pdfs():
    pdf_files = sorted(os.listdir(PDF_DIR))
    seen_cases = set()

    if os.path.exists(PHASE3_JSON):
        with open(PHASE3_JSON, encoding="utf-8") as f:
            for item in json.load(f):
                if item.get("Case Number"):
                    seen_cases.add(item["Case Number"])

    for idx, pdf_file in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}] Processing {pdf_file}...")
        result = process_pdf(pdf_file, seen_cases)

        if result:
            save_result(result)
            if result["Case Number"]:
                seen_cases.add(result["Case Number"])

        print("✅ Done\n")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    process_all_pdfs()
    print("🎯 Phase 3 COMPLETE")