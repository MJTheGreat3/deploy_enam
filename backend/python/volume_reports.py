import os
import requests
from datetime import datetime, timedelta
import pandas as pd

# === BASE DIRECTORY ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_CSV_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../frontend/static/assets/csv"))
VOLUME_DIR = os.path.join(BASE_CSV_DIR, "volume_reports")

def get_last_11_weekdays():
    dates = []
    current = datetime.now() - timedelta(days=1)
    while len(dates) < 11:
        if current.weekday() < 5:
            dates.append(current.strftime("%d%m%Y"))
        current -= timedelta(days=1)
    return dates

def disposer(directory, keep_filenames):
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath) and filename[:-4] not in keep_filenames:
            os.remove(filepath)
            print(f"Deleted: {filename}")

def filter_eq_series(csv_file):
    df = pd.read_csv(csv_file)
    df_filtered = df[df[" SERIES"] == " EQ"]
    df_filtered.to_csv(csv_file, index=False)
    print(f"Filtered file saved: {csv_file} (only ' EQ' series retained)")

def check_downloads(dates):
    base_url = "https://nsearchives.nseindia.com/products/content/"

    os.makedirs(VOLUME_DIR, exist_ok=True)

    for date in dates:
        filename = f"sec_bhavdata_full_{date}.csv"
        csv_url = base_url + filename
        local_csv_path = os.path.join(VOLUME_DIR, f"{date}.csv")

        if not os.path.exists(local_csv_path):
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.nseindia.com/",
                "Accept-Language": "en-US,en;q=0.9",
            }

            response = requests.get(csv_url, headers=headers)

            if response.status_code == 200:
                with open(local_csv_path, "wb") as f:
                    f.write(response.content)
                filter_eq_series(local_csv_path)
                print(f"Downloaded and saved as {local_csv_path}")
            else:
                print(f"Failed to download file for date {date}. Status code: {response.status_code}")
                return False

    disposer(VOLUME_DIR, dates)
    return True

def update_master_csv(csv_files, output_path=None):
    if output_path is None:
        output_path = os.path.join(BASE_CSV_DIR, "master.csv")

    data = {}

    for filename in csv_files:
        file_path = os.path.join(VOLUME_DIR, filename)
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found, skipping.")
            continue

        df = pd.read_csv(file_path, usecols=["SYMBOL", " TTL_TRD_QNTY", " DELIV_QTY"])

        df[" TTL_TRD_QNTY"] = pd.to_numeric(df[" TTL_TRD_QNTY"].astype(str).str.replace(",", ""), errors="coerce")
        df[" DELIV_QTY"] = pd.to_numeric(df[" DELIV_QTY"].astype(str).str.replace(",", ""), errors="coerce")
        df = df.dropna(subset=[" TTL_TRD_QNTY", " DELIV_QTY"])

        for _, row in df.iterrows():
            symbol = row["SYMBOL"]
            trd_qty = row[" TTL_TRD_QNTY"]
            deliv_qty = row[" DELIV_QTY"]

            if symbol not in data:
                data[symbol] = {
                    "TTL_TRD_QNTY_SUM": 0,
                    "DELIV_QTY_SUM": 0,
                    "COUNT": 0
                }

            data[symbol]["TTL_TRD_QNTY_SUM"] += trd_qty
            data[symbol]["DELIV_QTY_SUM"] += deliv_qty
            data[symbol]["COUNT"] += 1

    avg_data = []
    for symbol, stats in data.items():
        avg_trd_qty = stats["TTL_TRD_QNTY_SUM"] / stats["COUNT"]
        avg_deliv_qty = stats["DELIV_QTY_SUM"] / stats["COUNT"]
        avg_data.append({
            "SYMBOL": symbol,
            "AVG_TTL_TRD_QNTY": round(avg_trd_qty, 2),
            "AVG_DELIV_QTY": round(avg_deliv_qty, 2)
        })

    master_df = pd.DataFrame(avg_data)
    master_df.sort_values("SYMBOL", inplace=True)
    master_df.to_csv(output_path, index=False)
    print(f"Master file saved to {output_path}")

def compare_with_master(new_csv, master_csv=None):
    if master_csv is None:
        master_csv = os.path.join(BASE_CSV_DIR, "master.csv")

    new_csv_path = os.path.join(VOLUME_DIR, new_csv)

    master_df = pd.read_csv(master_csv)
    master_df.set_index("SYMBOL", inplace=True)

    df = pd.read_csv(new_csv_path, usecols=["SYMBOL", " TTL_TRD_QNTY", " DELIV_QTY"])
    df[" TTL_TRD_QNTY"] = pd.to_numeric(df[" TTL_TRD_QNTY"].astype(str).str.replace(",", ""), errors="coerce")
    df[" DELIV_QTY"] = pd.to_numeric(df[" DELIV_QTY"].astype(str).str.replace(",", ""), errors="coerce")
    df.dropna(subset=[" TTL_TRD_QNTY", " DELIV_QTY"], inplace=True)

    trd_devs = []
    deliv_devs = []

    for _, row in df.iterrows():
        symbol = row["SYMBOL"]
        new_trd = row[" TTL_TRD_QNTY"]
        new_deliv = row[" DELIV_QTY"]

        if symbol not in master_df.index:
            continue

        avg_trd = master_df.loc[symbol, "AVG_TTL_TRD_QNTY"]
        avg_deliv = master_df.loc[symbol, "AVG_DELIV_QTY"]

        if avg_trd and abs((new_trd - avg_trd) / avg_trd) >= 0.5:
            trd_devs.append({
                "SYMBOL": symbol,
                "AVG_TTL_TRD_QNTY": round(avg_trd, 2),
                "NEW_TTL_TRD_QNTY": new_trd,
                "PCT_DEVIATION": round(((new_trd - avg_trd) / avg_trd) * 100, 2)
            })

        if avg_deliv and abs((new_deliv - avg_deliv) / avg_deliv) >= 0.5:
            deliv_devs.append({
                "SYMBOL": symbol,
                "AVG_DELIV_QTY": round(avg_deliv, 2),
                "NEW_DELIV_QTY": new_deliv,
                "PCT_DEVIATION": round(((new_deliv - avg_deliv) / avg_deliv) * 100, 2)
            })

    pd.DataFrame(trd_devs).to_csv(os.path.join(BASE_CSV_DIR, "trd_deviation.csv"), index=False)
    pd.DataFrame(deliv_devs).to_csv(os.path.join(BASE_CSV_DIR, "deliv_deviation.csv"), index=False)

    print("Deviation reports saved as trd_deviation.csv and deliv_deviation.csv")

# === ENTRY POINT EXAMPLE ===
if __name__ == "__main__":
    last_11_dates = get_last_11_weekdays()

    if check_downloads(last_11_dates):
        for i in range(11):
            last_11_dates[i] += ".csv"

        update_master_csv(last_11_dates[1:])

        print(last_11_dates[0])
        compare_with_master(last_11_dates[0])
