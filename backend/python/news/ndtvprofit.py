import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
from filelock import FileLock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv")
CSV_FILE = os.path.abspath(CSV_FILE)
LOCK_FILE = CSV_FILE + ".lock"

SOURCE_NAME = "NDTV Profit"
BASE_URL = "https://www.ndtvprofit.com"
CUTOFF_TIME = datetime.now() - timedelta(hours=24)
ALLOWED_CATEGORIES = {"markets", "economy-finance", "ipos", "research-reports"}
COLUMNS = ["Source", "Headline", "Link", "Category", "Time"]

# === SETUP BROWSER ===
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

# === LOAD EXISTING HEADLINES FROM news_repository.csv ===
def load_existing_headlines():
    with FileLock(LOCK_FILE):
        if not os.path.exists(CSV_FILE):
            return set()
        df = pd.read_csv(CSV_FILE)
        if not all(col in df.columns for col in COLUMNS):
            df = pd.DataFrame(columns=COLUMNS)
            df.to_csv(CSV_FILE, index=False)
        return set(df["Headline"].dropna().tolist())

existing_headlines = load_existing_headlines()
session_headlines = set()

# === TIME PARSER ===
def parse_timestamp(time_str):
    try:
        time_str = time_str.strip()
        if not time_str:
            return None
        time_str = time_str.replace(" IST", "")
        return datetime.strptime(time_str, "%d %b %Y, %I:%M %p")
    except:
        return None

# === SCRAPING FUNCTION ===
def extract_articles():
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    containers = soup.find_all("div", class_=lambda x: x and "image-and-title-m__story-details" in x)
    results = []
    stop_flag = False

    for div in containers:
        try:
            a_tag = div.find("a", href=True)
            if not a_tag:
                continue

            h2_tag = a_tag.find("h2")
            if not h2_tag:
                continue

            headline = h2_tag.text.strip()
            link = BASE_URL + a_tag["href"]
            category = a_tag["href"].split("/")[1]

            time_div = div.find("div", class_=lambda x: x and "story-time" in x)
            time_str = time_div.text.strip() if time_div else ""
            dt = parse_timestamp(time_str)

            if not dt:
                continue
            if dt < CUTOFF_TIME:
                stop_flag = True
                break
            if headline in existing_headlines:
                stop_flag = True
                break
            if headline in session_headlines:
                continue
            if category not in ALLOWED_CATEGORIES:
                continue

            results.append({
                "Source": SOURCE_NAME,
                "Headline": headline,
                "Link": link,
                "Category": category,
                "Time": dt.isoformat()
            })
            session_headlines.add(headline)

        except:
            continue

    return results, stop_flag

# === MAIN SCRAPING LOOP ===
driver.get("https://www.ndtvprofit.com/the-latest?src=topnav")
time.sleep(5)

all_articles = []
should_stop = False

while not should_stop:
    batch, should_stop = extract_articles()
    all_articles.extend(batch)

    if not should_stop:
        buttons = driver.find_elements(By.XPATH, '//button[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "more stories")]')
        if not buttons:
            break

        try:
            time.sleep(2)  # polite delay before clicking
            driver.execute_script("arguments[0].click();", buttons[0])
            time.sleep(4)
        except:
            break

driver.quit()

# === SAVE TO news_repository.csv ===
if all_articles:
    new_df = pd.DataFrame(all_articles, columns=COLUMNS)
    with FileLock(LOCK_FILE):
        if os.path.exists(CSV_FILE):
            existing_df = pd.read_csv(CSV_FILE)
            if not all(col in existing_df.columns for col in COLUMNS):
                existing_df = pd.DataFrame(columns=COLUMNS)
            combined_df = pd.concat([new_df, existing_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=["Headline"])
        else:
            combined_df = new_df

        combined_df.to_csv(CSV_FILE, index=False)
