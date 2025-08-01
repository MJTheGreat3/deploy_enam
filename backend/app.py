from flask import Flask, render_template, request, jsonify
import csv
import os
import glob
import subprocess
import threading
import datetime
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from python.scrapers import company_data
from python import scraper
from python.ath_runner import run_ath_analysis
from flask_cors import CORS

app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static',
    static_url_path='/static'
)
CORS(app)

# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(SCRIPT_DIR, 'user_portfolio.csv')
LAST_UPDATED_DATA_FILE = os.path.join(SCRIPT_DIR, 'last_updated_data.txt')
LAST_UPDATED_NEWS_FILE = os.path.join(SCRIPT_DIR, 'last_updated_news.txt')

# === Locks ===
SCRIPT_LOCK = threading.Lock()
NEWS_SCRIPTS_WHITELIST = [
    'business_line.py', 'business_std.py', 'cnbctv_18.py',
    'econ_times.py', 'fin_exp.py', 'ft.py',
    'investing.py', 'money_control.py', 'ndtvprofit.py'
]
NEWS_SCRIPT_LOCKS = {script: threading.Lock() for script in NEWS_SCRIPTS_WHITELIST}

# === Helper Functions ===
def set_last_updated(file):
    with open(file, 'w') as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def get_last_updated(file):
    if not os.path.exists(file):
        return None
    with open(file, 'r') as f:
        return f.read().strip()
    
def latest_ath_file():
    files = [
        f for f in os.listdir('python')
        if f.startswith("ATH_companies_with_market_cap_") and f.endswith(".csv")
    ]
    if not files:
        return None
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join("python", f)))
    return os.path.join("python", latest)

def run_cleaner():
    logs = []
    cleaner_script = os.path.join('cleaner.py')
    if os.path.exists(os.path.join('python', 'cleaner.py')):
        logs.append("[INFO] Running cleaner.py...")
        try:
            result = subprocess.run(
                ['python', 'cleaner.py'],
                cwd='python',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            logs.append("[SUCCESS] cleaner.py completed.")
            if result.stdout:
                logs.append(result.stdout)
            if result.stderr:
                logs.append(f"[STDERR] {result.stderr}")
        except subprocess.CalledProcessError as e:
            logs.append(f"[ERROR] cleaner.py failed with code {e.returncode}")
            logs.append(e.stdout or "")
            logs.append(f"[STDERR] {e.stderr or ''}")
    else:
        logs.append("[WARNING] cleaner.py not found.")
    return logs

def run_python_script(script_path):
    logs = []
    script_name = os.path.basename(script_path)
    if not os.path.exists(script_path):
        logs.append(f"[ERROR] Script not found: {script_path}")
        return logs

    lock = NEWS_SCRIPT_LOCKS.get(script_name, SCRIPT_LOCK)
    with lock:
        logs.append(f"[INFO] Running: {script_path}")
        try:
            script_dir = os.path.dirname(script_path)
            result = subprocess.run(
                ['python', script_name],
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            logs.append(f"[SUCCESS] {script_path} completed.")
            if result.stdout:
                logs.append(result.stdout)
            if result.stderr:
                logs.append(f"[STDERR] {result.stderr}")
        except subprocess.CalledProcessError as e:
            logs.append(f"[ERROR] {script_path} failed with code {e.returncode}.")
            logs.append(e.stdout or "")
            logs.append(f"[STDERR] {e.stderr or ''}")
    return logs

def run_all_data_scripts():
    logs = []
    SCRIPTS = [
        'python/mutual_funds.py',
        'python/corp_actions.py',
        'python/volume_reports.py'
    ]

    logs.append("[INFO] Running bulk/block scrapers...")
    try:
        result = subprocess.run(
            ['python', 'scraper.py', 'all'],
            cwd='python',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logs.append("[SUCCESS] Bulk/Block scraping completed.")
        logs.append(result.stdout)
        if result.stderr:
            logs.append(f"[STDERR] {result.stderr}")
    except Exception as e:
        logs.append(f"[ERROR] Bulk/Block scraping failed: {str(e)}")

    for script in filter(os.path.exists, SCRIPTS):
        logs.extend(run_python_script(script))

    set_last_updated(LAST_UPDATED_DATA_FILE)
    return logs

def run_all_news_scripts():
    logs = []
    news_folder = os.path.join('python', 'news')
    scripts = [
        os.path.join(news_folder, s) for s in NEWS_SCRIPTS_WHITELIST
        if os.path.exists(os.path.join(news_folder, s))
    ]

    if not scripts:
        logs.append("[WARNING] No news scripts found to run.")
        return logs

    logs.append(f"[INFO] Found {len(scripts)} news scripts to run.")

    for script in scripts:
        logs.append(f"[INFO] Running news script: {script}")
        logs.extend(run_python_script(script))

        logs.append("[INFO] Running cleaner after news script.")
        logs.extend(run_cleaner())

    set_last_updated(LAST_UPDATED_NEWS_FILE)
    logs.append("[INFO] All news scripts (and cleaning) complete.")
    return logs

# === Company Scraper (Portfolio Changes) ===
def run_company_scrapers_async():
    def target():
        try:
            logs = []
            logs.append("[INFO] Running company data scrapers...")
            company_data.run_company_scrapers()
            logs.append("[SUCCESS] Company data scraping completed")
            print("\n".join(logs))
        except Exception as e:
            print(f"[ERROR] Company scraping failed: {str(e)}")

    threading.Thread(target=target, daemon=True).start()

# === ROUTES ===
@app.route('/')
def about():
    return render_template('about.html')

@app.route('/block-deals')
def block_deals():
    return render_template('block.html')

@app.route('/bulk-deals')
def bulk_deals():
    return render_template('bulk.html')

@app.route('/news')
def news():
    return render_template('news.html')

@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')

@app.route('/insider-deals')
def insider():
    return render_template('insider.html')

@app.route('/corp-announcements')
def announcements():
    return render_template('announcements.html')

@app.route('/corp-actions')
def actions():
    return render_template('actions.html')

@app.route('/mutual-funds')
def mutual_funds():
    return render_template('mf.html')

@app.route('/volume-reports')
def volume_reports():
    return render_template('volume.html')

# === Portfolio APIs ===
@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return jsonify([])
    portfolio = []
    with open(PORTFOLIO_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            portfolio.append({
                "symbol": row["symbol"],
                "name": row["name"],
                "status": row.get("status", "Old")
            })
    return jsonify(portfolio)

@app.route("/api/portfolio", methods=["POST"])
def add_portfolio():
    data = request.get_json()
    symbol = data.get("symbol")
    name = data.get("name")
    if not symbol or not name:
        return jsonify({"error": "Missing data"}), 400

    rows = []
    found = False

    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if row[0].upper() == symbol.upper():
                    row[2] = "New"
                    found = True
                rows.append(row)
    else:
        header = ["symbol", "name", "status"]

    if not found:
        rows.append([symbol.upper(), name, "New"])

    dir_path = os.path.dirname(PORTFOLIO_FILE)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(PORTFOLIO_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    return jsonify({"message": "Added"}), 200

@app.route("/api/portfolio", methods=["DELETE"])
def remove_portfolio():
    data = request.get_json()
    symbol = data.get("symbol")
    if not symbol or not os.path.exists(PORTFOLIO_FILE):
        return jsonify({"error": "Not found"}), 404

    rows = []
    with open(PORTFOLIO_FILE, "r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if row[0].upper() != symbol.upper():
                rows.append(row)

    with open(PORTFOLIO_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    return jsonify({"message": "Deleted"}), 200

@app.route("/api/portfolio/apply", methods=["POST"])
def apply_portfolio_changes():
    try:
        scraper.main("new")
        return jsonify({"message": "Scraper run"}), 200
    except Exception as e:
        print(f"[ERROR] Apply route: {e}")
        return jsonify({"error": "Scraper failed"}), 500

# === Refresh APIs ===
@app.route('/api/refresh-data-sync', methods=['POST'])
def refresh_data_sync():
    logs = run_all_data_scripts()
    return jsonify({
        "status": "success",
        "message": "Data refresh complete.",
        "logs": logs,
        "last_updated_data": get_last_updated(LAST_UPDATED_DATA_FILE)
    })

@app.route('/api/refresh-news-sync', methods=['POST'])
def refresh_news_sync():
    logs = run_all_news_scripts()
    return jsonify({
        "status": "success",
        "message": "News refresh complete.",
        "logs": logs,
        "last_updated_news": get_last_updated(LAST_UPDATED_NEWS_FILE)
    })

@app.route('/api/last-updated-data', methods=['GET'])
def last_updated_data():
    return jsonify({"last_updated_data": get_last_updated(LAST_UPDATED_DATA_FILE)})

@app.route('/api/last-updated-news', methods=['GET'])
def last_updated_news():
    return jsonify({"last_updated_news": get_last_updated(LAST_UPDATED_NEWS_FILE)})

@app.route("/api/ath/data", methods=["GET"])
def ath_data():
    filepath = latest_ath_file()
    if not filepath:
        return jsonify({"error": "No ATH data found"}), 404
    try:
        df = pd.read_csv(filepath)
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ath/refresh", methods=["POST"])
def refresh_ath_data():
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        output_file = run_ath_analysis(today)

        if output_file and os.path.exists(os.path.join("python", output_file)):
            return jsonify({"message": f"✅ Refreshed successfully", "file": output_file}), 200
        else:
            return jsonify({"error": "ATH refresh failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/ath-matrix')
def ath_matrix():
    # ⬅️ Modified to point to backend/csv/
    csv_dir = os.path.join(SCRIPT_DIR, "csv")
    csv_pattern = os.path.join(csv_dir, "ATH_companies_with_market_cap_*.csv")
    files = sorted(glob.glob(csv_pattern))

    if not files:
        return render_template("ath_matrix.html",
                               table=[],
                               dates=[],
                               company_details={},
                               total_companies=0,
                               total_dates=0,
                               error_message="No ATH CSV files found")

    presence = {}
    all_companies = set()
    all_dates = []
    company_details = {}

    for file in files:
        try:
            from datetime import datetime
            df = pd.read_csv(file)

            company_col = None
            for col in ["Company", "Company Name", "company", "company_name"]:
                if col in df.columns:
                    company_col = col
                    break

            if company_col is None:
                continue

            category_col = None
            for col in ["Category", "category", "Status"]:
                if col in df.columns:
                    category_col = col
                    break

            filename = os.path.basename(file)
            date_label = filename.replace("ATH_companies_with_market_cap_", "").replace(".csv", "")
            all_dates.append(date_label)

            for _, row in df.iterrows():
                company = str(row[company_col]).strip()
                if not company or company == 'nan':
                    continue

                all_companies.add(company)

                if company not in company_details:
                    sector = str(row.get('Sector', 'N/A')).strip()
                    industry = str(row.get('Industry', 'N/A')).strip()
                    market_cap = row.get('Market Cap (Cr)', 'N/A')

                    if sector == 'nan':
                        sector = 'N/A'
                    if industry == 'nan':
                        industry = 'N/A'

                    company_details[company] = {
                        'sector': sector,
                        'industry': industry,
                        'market_cap': market_cap,
                        'raw_market_cap': 0
                    }

                    if market_cap != 'N/A' and str(market_cap) != 'nan':
                        try:
                            market_cap_float = float(market_cap)
                            company_details[company]['raw_market_cap'] = market_cap_float
                            if market_cap_float >= 1000:
                                company_details[company]['market_cap_display'] = f"₹{market_cap_float/1000:.1f}K Cr"
                            else:
                                company_details[company]['market_cap_display'] = f"₹{market_cap_float:.1f} Cr"
                        except (ValueError, TypeError):
                            company_details[company]['market_cap_display'] = 'N/A'
                            company_details[company]['raw_market_cap'] = 0
                    else:
                        company_details[company]['market_cap_display'] = 'N/A'
                        company_details[company]['raw_market_cap'] = 0

                category_value = 0
                if category_col and category_col in row.index:
                    try:
                        category_value = int(row[category_col])
                    except (ValueError, TypeError):
                        category_str = str(row[category_col]).strip().lower()
                        if 'new ath' in category_str or category_str == '0':
                            category_value = 0
                        elif 'within 5%' in category_str or category_str == '5':
                            category_value = 5
                        elif 'within 10%' in category_str or category_str == '10':
                            category_value = 10
                        else:
                            category_value = 0

                if company not in presence:
                    presence[company] = {}

                presence[company][date_label] = {
                    "present": True,
                    "category": category_value
                }

        except Exception as e:
            continue

    all_companies = sorted(list(all_companies))

    def parse_date(date_str):
        try:
            day, month, year = date_str.split('_')
            return datetime(int(year), int(month), int(day))
        except (ValueError, AttributeError):
            return datetime(1900, 1, 1)

    formatted_dates = []

    for d in sorted(all_dates, key=parse_date, reverse=True):
      parsed = parse_date(d)
      display_label = parsed.strftime("%d %B %Y")  # e.g., "31 July 2025"
      formatted_dates.append((d, display_label))

    table_data = []
    for company in all_companies:
        details = company_details.get(company, {})
        row = {
            'company': company,
            'sector': details.get('sector', 'N/A'),
            'industry': details.get('industry', 'N/A'),
            'market_cap': details.get('market_cap_display', 'N/A'),
            'raw_market_cap': details.get('raw_market_cap', 0),
            'presence': {}
        }

        for date in all_dates:
            company_presence = presence.get(company, {}).get(date, {"present": False, "category": None})

            if company_presence["present"]:
                category = company_presence["category"]
                if category == 0:
                    row['presence'][date] = {"status": "Yes", "class": "new-ath", "category": 0}
                elif category == 5:
                    row['presence'][date] = {"status": "Yes", "class": "within-5", "category": 5}
                elif category == 10:
                    row['presence'][date] = {"status": "No", "class": "within-10", "category": 10}
                else:
                    row['presence'][date] = {"status": "Yes", "class": "new-ath", "category": 0}
            else:
                row['presence'][date] = {"status": "No", "class": "not-present", "category": None}

        table_data.append(row)

    return render_template("ath_matrix.html",
                       table=table_data,
                       dates=formatted_dates,
                       company_details=company_details,
                       total_companies=len(all_companies),
                       total_dates=len(all_dates))

# === Scheduler ===
def run_scheduled_jobs():
    print("[INFO] Checking whether initial data and news updates are needed...")
    now = datetime.datetime.now()

    last_data_str = get_last_updated(LAST_UPDATED_DATA_FILE)
    data_needs_update = not last_data_str or \
        (now - datetime.datetime.strptime(last_data_str, "%Y-%m-%d %H:%M:%S")).total_seconds() > 3 * 60 * 60

    last_news_str = get_last_updated(LAST_UPDATED_NEWS_FILE)
    news_needs_update = not last_news_str or \
        (now - datetime.datetime.strptime(last_news_str, "%Y-%m-%d %H:%M:%S")).total_seconds() > 10 * 60

    def background_job():
        logs = []
        if data_needs_update:
            logs.extend(run_all_data_scripts())
        if news_needs_update:
            logs.extend(run_all_news_scripts())
        print("[INITIAL SCHEDULED RUN LOGS]")
        print("\n".join(logs))

    if data_needs_update or news_needs_update:
        threading.Thread(target=background_job, daemon=True).start()
    else:
        print("[INFO] No initial refresh needed.")

def run_quarterly_ath_if_needed():
    today = datetime.datetime.today()
    if today.month in [1, 4, 7, 10] and today.day == 1:
        print(f"[⏰] Running Quarterly ATH refresh for {today.strftime('%Y-%m-%d')}")
        run_ath_analysis(today.strftime('%Y-%m-%d'))

# === MAIN ===
if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_all_data_scripts, 'interval', minutes=180)
    scheduler.add_job(run_all_news_scripts, 'interval', minutes=10)
    scheduler.start()
    print("[INFO] Scheduler started.")
    run_scheduled_jobs()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
