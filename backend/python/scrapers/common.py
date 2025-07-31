import os
import csv
import threading
import psutil
import gc
import time
import pandas as pd
from datetime import datetime

# === PATH CONFIGURATION ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../frontend/static/assets/csv"))
LOG_FILE_PATH = os.path.join(SCRIPT_DIR, "scraper_log.txt")
USER_PORTFOLIO_CSV = os.path.abspath(os.path.join(SCRIPT_DIR, "../../user_portfolio.csv"))

# === FILE LOCKS ===
file_locks = {
    "bulk_deals.csv": threading.Lock(),
    "block_deals.csv": threading.Lock(),
    "announcements.csv": threading.Lock(),
    "insider_trading.csv": threading.Lock()
}

def get_csv_path(filename):
    return os.path.join(CSV_DIR, filename)

def log_debug(message):
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{timestamp} {message}\n")

def load_portfolio_symbols(only_new=False):
    if not os.path.isfile(USER_PORTFOLIO_CSV):
        print(f"[WARN] user_portfolio.csv not found at {USER_PORTFOLIO_CSV}")
        return []
    try:
        df = pd.read_csv(USER_PORTFOLIO_CSV)
        if 'symbol' not in df.columns:
            print(f"[ERROR] 'symbol' column missing in user_portfolio.csv")
            return []
        if only_new and 'status' in df.columns:
            df = df[df['status'].str.upper() == "NEW"]
        symbols = sorted(set(df['symbol'].dropna().str.strip().str.upper()))
        print(f"[INFO] Loaded {len(symbols)} symbols from user_portfolio.csv")
        return symbols
    except Exception as e:
        print(f"[ERROR] Could not read user_portfolio.csv: {e}")
        return []

def append_unique_rows(csv_filename, new_rows, header=None):
    full_path = get_csv_path(csv_filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with file_locks[csv_filename]:
        existing = set()

        if os.path.isfile(full_path):
            with open(full_path, 'r', newline='') as f:
                reader = csv.reader(f)
                if header:
                    try:
                        next(reader)
                    except StopIteration:
                        pass
                existing.update(tuple(row) for row in reader)

        unique = [row for row in new_rows if tuple(row) not in existing]

        if unique:
            mode = 'a' if os.path.isfile(full_path) else 'w'
            with open(full_path, mode, newline='') as f:
                writer = csv.writer(f)
                if mode == 'w' and header:
                    writer.writerow(header)
                writer.writerows(unique)

def remove_duplicates_from_csv_with_header(file_path):
    seen = set()
    with open(file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return

        rows = [row for row in reader if tuple(row) not in seen and not seen.add(tuple(row))]

    date_col_index = None
    for idx, col in enumerate(header):
        if "date" in col.lower():
            date_col_index = idx
            break

    def parse_date_safe(date_str):
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        return datetime.min

    if date_col_index is not None:
        rows.sort(key=lambda row: parse_date_safe(row[date_col_index]))

    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

def check_system_resources():
    cpu_threshold = 80
    mem_threshold = 85
    wait_time = 5
    max_attempts = 5

    attempt = 0
    while attempt < max_attempts:
        cpu_usage = psutil.cpu_percent(interval=1)
        mem_usage = psutil.virtual_memory().percent
        if cpu_usage < cpu_threshold and mem_usage < mem_threshold:
            return
        print(f"[WARN] High usage - CPU: {cpu_usage}%, Mem: {mem_usage}% - GC Attempt {attempt+1}")
        gc.collect()
        attempt += 1
        time.sleep(wait_time)
    raise Exception("Resources too constrained after attempts.")

def convert_nse_datetime(raw):
    try:
        dt = datetime.strptime(raw.strip(), "%d-%b-%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return raw
