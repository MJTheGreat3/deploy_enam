import os
import csv
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd
from filelock import FileLock

# Constants
BASE_URL = "https://www.business-standard.com/latest-news"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = REPO_FILE + ".lock"

ALLOWED_CATEGORIES = {"companies", "economy", "markets", "industry", "finance"}
COLUMNS = ["Source", "Headline", "Link", "Category", "Time"]

# How far back to allow
MAX_AGE_HOURS = 24

# ----------------------------------------------------------------------------
def parse_bs_timestamp(time_text):
    try:
        time_text = time_text.replace("Updated On :", "").strip()
        time_text = time_text.lower().replace('ist', '').strip()

        is_premium = False
        if 'premium' in time_text:
            is_premium = True
            time_text = time_text.replace('premium', '').strip()

        parts = time_text.split('|')
        if len(parts) != 2:
            return None, False

        date_part = parts[0].strip().title()
        time_part = parts[1].strip().upper()
        clean_time_str = f"{date_part} | {time_part}"

        dt = datetime.strptime(clean_time_str, "%d %b %Y | %I:%M %p")
        return dt, is_premium

    except Exception:
        return None, False

# ----------------------------------------------------------------------------
def load_existing_links():
    if not os.path.exists(REPO_FILE):
        return set()
    try:
        df = pd.read_csv(REPO_FILE)
        return set(df['Link'].dropna().values)
    except Exception:
        return set()

# ----------------------------------------------------------------------------
def extract_articles_from_soup(soup, existing_links, cutoff_datetime):
    container = soup.find('div', class_='article-listing')
    if not container:
        return [], True

    articles = container.find_all('div', class_='listingstyle_cardlistlist__dfq57 cardlist')
    new_entries = []
    stop = False

    for article in articles:
        headline_tag = article.find('a', class_='smallcard-title')
        if not headline_tag:
            continue

        link = headline_tag['href'].strip()
        headline = headline_tag.text.strip()

        if link in existing_links:
            stop = True
            break

        time_div = article.find('div', class_='listingstyle_timestmp__VSJNW')
        raw_time_text = time_div.get_text(strip=True) if time_div else ""
        parsed_dt, is_premium = parse_bs_timestamp(raw_time_text)
        if not parsed_dt:
            continue

        if parsed_dt < cutoff_datetime:
            stop = True
            break

        if is_premium:
            headline = f"[Premium] {headline}"

        try:
            category = link.split("/")[3].lower() if len(link.split("/")) > 3 else ""
        except IndexError:
            category = ""

        if category not in ALLOWED_CATEGORIES:
            continue

        new_entries.append({
            "Source": "Business Standard",
            "Headline": headline,
            "Link": link,
            "Category": category,
            "Time": parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
        })

    return new_entries, stop

# ----------------------------------------------------------------------------
def main():
    cutoff_datetime = datetime.now() - timedelta(hours=MAX_AGE_HOURS)
    existing_links = load_existing_links()

    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=chrome_options)

    all_new_entries = []
    page_number = 1
    stop_scraping = False

    while not stop_scraping:
        page_url = BASE_URL if page_number == 1 else f"{BASE_URL}/page-{page_number}"
        driver.get(page_url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        new_entries, stop_scraping = extract_articles_from_soup(soup, existing_links, cutoff_datetime)

        all_new_entries.extend(new_entries)

        if stop_scraping:
            break

        page_number += 1

    driver.quit()

    if not all_new_entries:
        print("No new articles added from Business Standard.")
        return

    with FileLock(LOCK_FILE):
        if os.path.exists(REPO_FILE):
            existing_df = pd.read_csv(REPO_FILE)
            combined_df = pd.concat([pd.DataFrame(all_new_entries, columns=COLUMNS), existing_df], ignore_index=True)
            combined_df.drop_duplicates(subset=["Link"], inplace=True, keep='first')
        else:
            combined_df = pd.DataFrame(all_new_entries, columns=COLUMNS)

        combined_df.to_csv(REPO_FILE, index=False)

    print(f"{len(all_new_entries)} articles added from Business Standard.")

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
