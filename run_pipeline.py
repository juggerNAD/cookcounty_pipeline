import subprocess
import sys
from pathlib import Path
import pandas as pd
import json

# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_EXCEL = BASE_DIR / "final_pipeline_results.xlsx"

PHASES = [
    ("Phase1", "phase1_scraper.py", "phase1_results.csv", "phase1_results.json"),
    ("Phase2", "phase2_scraper.py", "phase2_results.csv", "phase2_results.json"),
    ("Phase3", "phase3_results.py", "phase3_results.csv", "phase3_results.json"),
    ("Phase4", "phase4_results.py", "phase4_results.csv", "phase4_results.json"),
]

# =========================
# ENSURE JSON FILES EXIST
# =========================

for _, _, _, json_file in PHASES:
    path = BASE_DIR / json_file
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
        print(f"📝 Created empty JSON: {json_file}")

# =========================
# RUN A PHASE SCRIPT
# =========================

def run_phase(name, script):
    print(f"\n🚀 Running {name}")
    result = subprocess.run([sys.executable, str(BASE_DIR / script)], cwd=BASE_DIR)
    
    if result.returncode != 0:
        # Phase stopped due to duplicates is NOT a failure
        print(f"⚠ {name} stopped (likely no new data). Continuing to next phase...")
        return False
    
    print(f"✅ {name} completed")
    return True

# =========================
# WRITE CSV TO EXCEL SHEET
# =========================

def write_excel_sheet(sheet_name, csv_file):
    csv_path = BASE_DIR / csv_file
    if not csv_path.exists():
        print(f"⚠ CSV not found for {sheet_name}, skipping")
        return 0

    df = pd.read_csv(csv_path)
    new_records = len(df)

    mode = "a" if OUTPUT_EXCEL.exists() else "w"
    kwargs = {"engine": "openpyxl", "mode": mode}
    if mode == "a":
        kwargs["if_sheet_exists"] = "replace"

    with pd.ExcelWriter(OUTPUT_EXCEL, **kwargs) as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"📄 {sheet_name} written to Excel ({new_records} records)")
    return new_records

# =========================
# MAIN PIPELINE
# =========================

def main():
    for name, script, csv_file, _ in PHASES:
        # Run the phase
        run_phase(name, script)

        # Consolidate CSV into centralized Excel and log new records
        count = write_excel_sheet(name, csv_file)
        if count == 0:
            print(f"⚠ {name} had no new records today")

    print("\n🎯 ALL PHASES COMPLETE")
    print(f"📊 Centralized Excel: {OUTPUT_EXCEL}")
    print("📁 CSV and JSON files are saved in the app directory.")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
