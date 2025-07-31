import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd
import os
import threading
import time
from datetime import datetime, timedelta

# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_FILE = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv")
)
SOURCE = "Money Control"
DATE_CUTOFF = datetime.now() - timedelta(hours=24)

CATEGORIES = {
    "economy": "https://www.moneycontrol.com/news/business/economy",
    "companies": "https://www.moneycontrol.com/news/business/companies",
    "ipo": "https://www.moneycontrol.com/news/business/ipo",
    "stocks": "https://www.moneycontrol.com/news/business/stocks",
    "commodities": "https://www.moneycontrol.com/news/business/commodities",
    "real-estate": "https://www.moneycontrol.com/news/business/real-estate",
}

csv_lock = threading.Lock()

# === LOAD EXISTING LINKS ===
if os.path.exists(NEWS_FILE):
    df_all = pd.read_csv(NEWS_FILE)
    existing_links = set(df_all['Link'].tolist())
else:
    df_all = pd.DataFrame(columns=['Source','Headline','Link','Category','Time'])
    existing_links = set()

# === TIME PARSER ===
def parse_time(text):
    text = text.replace(' IST','').strip()
    try:
        return datetime.strptime(text, "%B %d, %Y %I:%M %p")
    except Exception:
        return None

# === SCRAPE ONE PAGE ===
def scrape_page(url, category):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return [], False
    except Exception:
        return [], False

    soup = BeautifulSoup(resp.text, 'html.parser')
    articles = soup.find_all('li', class_='clearfix')

    rows = []
    stop_signal = False

    for art in articles:
        try:
            a_tag = art.find('a', href=True, title=True)
            if not a_tag:
                continue

            link = a_tag['href']
            headline = a_tag['title'].strip()

            # === TIME EXTRACTION ===
            time_text = ""
            time_span = art.find('span')
            if time_span:
                time_text = time_span.get_text(strip=True)

            if not time_text:
                comments = art.find_all(string=lambda text: isinstance(text, Comment))
                for comment in comments:
                    if '<span>' in comment:
                        soup2 = BeautifulSoup(comment, 'html.parser')
                        span = soup2.find('span')
                        if span:
                            time_text = span.get_text(strip=True)
                            break

            if not time_text:
                continue

            dt = parse_time(time_text)
            if not dt:
                continue

            if dt < DATE_CUTOFF:
                stop_signal = True
                break

            with csv_lock:
                if link in existing_links:
                    stop_signal = True
                    break

            # Valid new row
            rows.append({
                "Source": SOURCE,
                "Headline": headline,
                "Link": link,
                "Category": category,
                "Time": dt.isoformat()
            })

        except Exception:
            continue

    return rows, stop_signal

# === THREAD WORKER ===
def scrape_category(category, base_url):
    page_num = 1

    while True:
        page_url = base_url if page_num == 1 else f"{base_url}/page-{page_num}"
        rows, stop = scrape_page(page_url, category)

        if rows:
            with csv_lock:
                if os.path.exists(NEWS_FILE):
                    df_current = pd.read_csv(NEWS_FILE)
                else:
                    df_current = pd.DataFrame(columns=['Source','Headline','Link','Category','Time'])

                df_new = pd.DataFrame(rows)
                combined = pd.concat([df_new, df_current], ignore_index=True)
                combined = combined.drop_duplicates(subset=['Link'])

                combined.to_csv(NEWS_FILE, index=False)
                existing_links.update(df_new['Link'].tolist())

        if stop or not rows:
            break

        page_num += 1
        time.sleep(1)

# === START THREADS ===
threads = []
for cat, url in CATEGORIES.items():
    t = threading.Thread(target=scrape_category, args=(cat, url))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
