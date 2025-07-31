import os
import time
import csv
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
from filelock import FileLock

# ----------------------------------------------------------------------------
# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_REPO = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = NEWS_REPO + ".lock"
SOURCE = "Hindu Business Line"
ALLOWED_CATEGORIES = {
    "Commodities",
    "Companies",
    "Economy",
    "Markets",
    "Money & Banking",
    "Stocks"
}

URL = "https://www.thehindubusinessline.com/latest-news/"
NOW_UTC = datetime.now(timezone.utc)
TIME_CUTOFF = NOW_UTC - timedelta(hours=24)

COLUMNS = ["Source", "Headline", "Link", "Category", "Time"]

# ----------------------------------------------------------------------------
def safe_print(*args, **kwargs):
    text = " ".join(str(arg) for arg in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        # Replace problematic characters with '?'
        print(text.encode('ascii', errors='replace').decode('ascii'), **kwargs)

# ----------------------------------------------------------------------------
def load_existing_links():
    if not os.path.exists(NEWS_REPO):
        return set()
    try:
        df = pd.read_csv(NEWS_REPO)
        return set(df['Link'].dropna().values)
    except Exception as e:
        safe_print("[WARN] Error reading existing repository:", e)
        return set()

# ----------------------------------------------------------------------------
def main():
    safe_print("[START] HBL Scraper")
    existing_links = load_existing_links()

    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(URL)
    time.sleep(5)  # Wait for page to load

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    news_div = soup.find('div', class_='fgdf')
    if not news_div:
        safe_print("[ERROR] No news container found.")
        return

    news_items = news_div.find_all('li')
    new_entries = []

    for item in news_items:
        a_tag = item.find('a', href=True)
        if not a_tag:
            continue

        link = a_tag['href'].strip()
        label = a_tag.find('div', class_='label').text.strip() if a_tag.find('div', class_='label') else ""
        time_str = a_tag.find('div', class_='time').text.strip() if a_tag.find('div', class_='time') else ""
        title = a_tag.find('h3', class_='title').text.strip() if a_tag.find('h3', class_='title') else ""

        # Stop if older than 24 hours
        try:
            article_dt = datetime.strptime(time_str, "%H:%M | %b %d, %Y")
            article_dt = article_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            safe_print("[WARN] Unable to parse time:", time_str)
            continue

        if article_dt < TIME_CUTOFF:
            safe_print("[STOP] Encountered article older than 24 hours:", time_str)
            break

        # Stop if duplicate
        if link in existing_links:
            safe_print("[STOP] Duplicate article found:", link)
            break

        # Filter categories
        if label not in ALLOWED_CATEGORIES:
            safe_print("[SKIP] Category not allowed:", label, "|", title)
            continue

        safe_print("[NEW] Collected:", label, "|", title)

        new_entries.append({
            "Source": SOURCE,
            "Headline": title,
            "Link": link,
            "Category": label,
            "Time": time_str
        })

    if not new_entries:
        safe_print("[INFO] No new articles found.")
        return

    # ----------------------------------------------------------------------------
    # Save to news_repository.csv with locking
    with FileLock(LOCK_FILE):
        safe_print("[LOCK] Acquired lock for writing")
        if os.path.exists(NEWS_REPO):
            existing_df = pd.read_csv(NEWS_REPO)
            combined_df = pd.concat([pd.DataFrame(new_entries, columns=COLUMNS), existing_df], ignore_index=True)
            combined_df.drop_duplicates(subset=["Link"], inplace=True, keep='first')
        else:
            combined_df = pd.DataFrame(new_entries, columns=COLUMNS)

        combined_df.to_csv(NEWS_REPO, index=False)
        safe_print("[SAVE]", len(new_entries), "new articles added to", NEWS_REPO)

    safe_print("[DONE] HBL scraping complete.")

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
