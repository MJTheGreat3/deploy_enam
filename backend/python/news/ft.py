from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import pandas as pd
import os
from filelock import FileLock

# ------------------ CONFIG ------------------
BASE_URL = "https://www.ft.com/news-feed"

# Compute absolute path to CSV file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = CSV_FILE + ".lock"

SOURCE_NAME = "Financial Times"
COLUMNS = ["Source", "Headline", "Link", "Category", "Time"]

ALLOWED_CATEGORIES = [
    "Markets", "Banking", "Asset", "Business", "Stock",
    "Companies", "Investment", "Private equity", "Economy", "Oil & Gas"
]

CUTOFF_TIME = datetime.now() - timedelta(hours=24)

# ------------------ SETUP CHROME ------------------
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)

# ------------------ LOAD EXISTING ------------------
with FileLock(LOCK_FILE):
    if os.path.exists(CSV_FILE):
        existing_df = pd.read_csv(CSV_FILE)
        if not all(col in existing_df.columns for col in COLUMNS):
            existing_df = pd.DataFrame(columns=COLUMNS)
        existing_urls = set(existing_df["Link"].dropna().tolist())
        existing_titles = set(existing_df["Headline"].dropna().tolist())
    else:
        existing_df = pd.DataFrame(columns=COLUMNS)
        existing_urls = set()
        existing_titles = set()

# ------------------ HELPERS ------------------
def is_relevant_category(category_text):
    return any(key.lower() in category_text.lower() for key in ALLOWED_CATEGORIES)

def parse_article_date(date_text):
    try:
        return datetime.strptime(date_text, "%B %d %Y")
    except Exception:
        return None

def parse_page_articles(page_source):
    soup = BeautifulSoup(page_source, 'html.parser')
    items = soup.find_all("li", class_="o-teaser-collection__item")
    articles = []
    stop_scraping = False

    for item in items:
        # --- Date parsing ---
        time_tag = item.find("time")
        if not time_tag:
            continue

        date_text = time_tag.get_text(strip=True)
        article_date = parse_article_date(date_text)
        if not article_date:
            continue

        if article_date < CUTOFF_TIME:
            stop_scraping = True
            break

        # --- Category parsing ---
        category_tag = item.find("a", class_="o-teaser__tag")
        category = category_tag.get_text(strip=True) if category_tag else "Uncategorized"
        if not is_relevant_category(category):
            continue

        # --- Headline and Link ---
        headline_tag = item.find("a", class_="js-teaser-heading-link")
        if not headline_tag or not headline_tag.has_attr("href"):
            continue

        url = "https://www.ft.com" + headline_tag['href']
        headline = headline_tag.get_text(strip=True)

        # --- Duplicate check ---
        if url in existing_urls or headline in existing_titles:
            stop_scraping = True
            break

        # --- Add article ---
        articles.append({
            "Source": SOURCE_NAME,
            "Headline": headline,
            "Link": url,
            "Category": category,
            "Time": article_date.strftime("%Y-%m-%d %H:%M:%S")
        })

    return articles, stop_scraping

# ------------------ MAIN SCRAPER ------------------
all_articles = []
page = 1
while True:
    print(f"Scraping FT page {page}")
    url = f"{BASE_URL}?page={page}"
    driver.get(url)
    time.sleep(5)

    new_articles, stop = parse_page_articles(driver.page_source)
    print(f"Found {len(new_articles)} new articles on page {page}")

    all_articles.extend(new_articles)

    if stop:
        print("Stopping: found older or duplicate article")
        break

    page += 1

driver.quit()

# ------------------ SAVE RESULTS ------------------
if all_articles:
    new_df = pd.DataFrame(all_articles, columns=COLUMNS)
    with FileLock(LOCK_FILE):
        if os.path.exists(CSV_FILE):
            existing_df = pd.read_csv(CSV_FILE)
            if not all(col in existing_df.columns for col in COLUMNS):
                existing_df = pd.DataFrame(columns=COLUMNS)
            combined_df = pd.concat([new_df, existing_df], ignore_index=True)
        else:
            combined_df = new_df

        combined_df.to_csv(CSV_FILE, index=False)

    print(f"{len(all_articles)} articles added from Financial Times.")
else:
    print("No new articles found to add.")
