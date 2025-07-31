import os
import io
import time
from datetime import datetime
import pandas as pd
import win32com.client as win32
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# === PATH SETUP ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../frontend/static/assets/csv"))
DATA_OUTPUT = os.path.join(ASSETS_DIR, "data.xlsx")
PROCESSED_FILE = os.path.join(SCRIPT_DIR, "processed.txt")
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp_xlsm")

# === CONFIGURATION ===
FOLDER_ID = '1koWJVR3mykJZT0RT2YaLdp0Yx9XbIQqb'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
MACRO_NAME = 'Module17.CP_AMCViewAll'
SHEET_NAME = 'Complete Portfolio'

# === LOGGING ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_msg = f"{timestamp} {message}"
    print(full_msg)

# === GOOGLE AUTH ===
def authenticate():
    log("Authenticating with Google API...")
    creds = None
    token_path = os.path.join(SCRIPT_DIR, 'token.json')
    secret_path = os.path.join(SCRIPT_DIR, 'client_secret.json')

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            log(f"Token invalid or corrupted, deleting token.json: {e}")
            os.remove(token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log(f"Refresh failed: {e}")
                os.remove(token_path)
                return authenticate()
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

# === PROCESSED FILE TRACKING ===
def get_processed_files():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, 'r') as f:
        return set(line.strip() for line in f)

def mark_file_as_processed(name):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(name + '\n')

# === DOWNLOAD FROM DRIVE ===
def download_file(service, file_id, name):
    os.makedirs(TEMP_DIR, exist_ok=True)
    path = os.path.join(TEMP_DIR, name)
    log(f"Downloading {name}...")
    request = service.files().get_media(fileId=file_id)
    with open(path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    log(f"Downloaded to {path}")
    return path

# === RUN MACRO AND EXTRACT DATA ===
def run_macro_and_extract_data(xlsm_path, output_path):
    log("Launching Excel...")
    excel = win32.gencache.EnsureDispatch('Excel.Application')
    excel.Visible = False
    wb = excel.Workbooks.Open(os.path.abspath(xlsm_path))
    log(f"Running macro: {MACRO_NAME}")
    excel.Application.Run(MACRO_NAME)
    time.sleep(2)

    log(f"Accessing worksheet: {SHEET_NAME}")
    ws = wb.Sheets(SHEET_NAME)
    processed_data = []
    row = 11
    empty_streak = 0
    included_rows = 0
    skipped_rows = 0

    log("Starting data extraction...")
    while empty_streak < 10:
        fund = ws.Cells(row, 2).Value
        stock = ws.Cells(row, 3).Value
        value = ws.Cells(row, 9).Value

        if fund is None and stock is None and value is None:
            empty_streak += 1
            row += 1
            continue
        else:
            empty_streak = 0

        if value is None or value == 0:
            log(f"Row {row}: Skipped (I is 0 or empty)")
            skipped_rows += 1
            row += 1
            continue

        buy = abs(value) if value > 0 else 0
        sell = abs(value) if value < 0 else 0
        processed_data.append([stock, fund, buy, sell])
        log(f"Row {row}: Included | Stock: {stock}, Fund: {fund}, Buy: {buy}, Sell: {sell}")
        included_rows += 1
        row += 1

    df = pd.DataFrame(processed_data, columns=["Stock", "Fund", "Buy", "Sell"])
    df.to_excel(output_path, index=False)

    wb.Close(False)
    excel.Quit()

    log("\nExtraction complete.")
    log(f"Total rows included: {included_rows}")
    log(f"Total rows skipped: {skipped_rows}")
    log(f"Output saved to: {output_path}")

# === MAIN ===
def main():
    service = authenticate()
    processed = get_processed_files()

    query = f"'{FOLDER_ID}' in parents and mimeType='application/vnd.ms-excel.sheet.macroEnabled.12'"
    results = []
    seen = set()
    token = None

    while True:
        response = service.files().list(
            q=query, spaces='drive',
            fields="nextPageToken, files(id, name)", pageSize=100,
            pageToken=token
        ).execute()
        for file in response.get('files', []):
            if file['name'] not in seen:
                seen.add(file['name'])
                results.append(file)
        token = response.get('nextPageToken')
        if not token:
            break

    for file in results:
        name, fid = file['name'], file['id']
        if name in processed:
            log(f"Skipping {name} (already processed)")
            continue

        xlsm_path = None
        try:
            log(f"\n=== Processing: {name} ===")
            xlsm_path = download_file(service, fid, name)
            run_macro_and_extract_data(xlsm_path, DATA_OUTPUT)
            mark_file_as_processed(name)
        except Exception as e:
            log(f"❌ Error processing {name}: {e}")
        finally:
            if xlsm_path and os.path.exists(xlsm_path):
                os.remove(xlsm_path)
                log(f"Deleted downloaded file: {xlsm_path}")

if __name__ == "__main__":
    main()
