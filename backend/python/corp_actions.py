import requests
import pandas as pd
import os
from datetime import datetime, timedelta

# === PATH SETUP ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../frontend/static/assets/csv"))
MAIN_CSV = os.path.join(ASSETS_DIR, "corp_actions.csv")
TEMP_CSV = os.path.join(ASSETS_DIR, "downloaded.csv")

# === FUNCTIONS ===

def download_bse_csv(temp_file):
    """Download CSV exactly like BSE site does"""
    url = "https://api.bseindia.com/BseIndiaAPI/api/CorpactCSVDownload/w"

    # Mimic site: empty Fdate/TDate = full data
    params = {
        "scripcode": "",
        "Fdate": "",
        "TDate": "",
        "Purposecode": "",
        "strSearch": "S",
        "ddlindustrys": "",
        "ddlcategorys": "E",
        "segment": "0"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bseindia.com/"
    }

    print("[DEBUG] Sending request to BSE...")
    response = requests.get(url, headers=headers, params=params)
    if response.ok:
        with open(temp_file, "wb") as f:
            f.write(response.content)
        print(f"[DEBUG] Downloaded BSE CSV to {temp_file}")
    else:
        raise Exception(f"[ERROR] Failed to download: {response.status_code}")

def ensure_main_csv_exists(header):
    """If main CSV does not exist, create it with header"""
    if not os.path.exists(MAIN_CSV):
        print("[DEBUG] Main CSV not found. Creating new with header.")
        empty_df = pd.DataFrame(columns=header)
        empty_df.to_csv(MAIN_CSV, index=False)
    else:
        print("[DEBUG] Main CSV already exists.")

def load_csv(file):
    """Load a CSV into DataFrame"""
    print(f"[DEBUG] Loading CSV: {file}")
    df = pd.read_csv(file)
    print(f"[DEBUG] Loaded {len(df)} rows.")
    return df

def parse_date_safe(date_str):
    """
    Parse BSE date format like '27 Jun 2025'.
    Return None if missing or invalid.
    """
    if not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d %b %Y")
    except ValueError:
        return None

def filter_by_date_window(df):
    """
    Keep only records with Record Date or Ex Date in next 2 months (inclusive).
    """
    print("[DEBUG] Filtering by date window...")
    today = datetime.today().date()
    two_months = today + timedelta(days=61)

    record_dates = df['Record Date'].apply(parse_date_safe)
    ex_dates = df['Ex Date'].apply(parse_date_safe)

    def is_in_range(date_val):
        if date_val is None:
            return False
        d = date_val.date()
        return today <= d <= two_months

    keep_mask = record_dates.apply(is_in_range) | ex_dates.apply(is_in_range)
    filtered = df[keep_mask]
    print(f"[DEBUG] Rows after filtering: {len(filtered)}")
    return filtered

def main():
    print("[INFO] Starting corporate actions update process...")

    # Step 1: Download BSE CSV to temp
    download_bse_csv(TEMP_CSV)

    # Step 2: Load the downloaded CSV
    downloaded_df = load_csv(TEMP_CSV)

    if downloaded_df.empty:
        print("[WARN] Downloaded CSV is empty. Nothing to do.")
        os.remove(TEMP_CSV)
        return

    # Step 3: Ensure main CSV exists
    ensure_main_csv_exists(header=downloaded_df.columns)

    # Step 4: Load existing corpus
    main_df = load_csv(MAIN_CSV)

    # Step 5: Concatenate and drop duplicates
    combined_df = pd.concat([main_df, downloaded_df])
    combined_df = combined_df.drop_duplicates()
    print(f"[DEBUG] Combined unique rows: {len(combined_df)}")

    # Step 6: Filter for date window
    filtered_df = filter_by_date_window(combined_df)

    # Step 7: Keep only desired columns
    desired_cols = [
        "Security Code","Security Name","Company Name","Ex Date","Purpose",
        "Record Date","BC Start Date","BC End Date","ND Start Date","ND End Date","Actual Payment Date"
    ]
    filtered_df = filtered_df[desired_cols]

    # Step 8: Write back to MAIN CSV
    filtered_df.to_csv(MAIN_CSV, index=False)
    print(f"[INFO] Saved updated corpus to {MAIN_CSV}")

    # Step 9: Delete temp file
    os.remove(TEMP_CSV)
    print(f"[INFO] Deleted temp file {TEMP_CSV}")

    print("[INFO] Corporate actions update complete.")

if __name__ == "__main__":
    main()
