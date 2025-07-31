import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime, timedelta, timezone
import os
from filelock import FileLock

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
BASE_URL = "https://www.financialexpress.com/latest-news/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = CSV_FILE + ".lock"
SOURCE = "Financial Express"
TIME_LIMIT = datetime.now(timezone.utc) - timedelta(hours=24)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

VALID_CATEGORIES = {
    "banking-finance",
    "business",
    "economy",
    "industry",
    "ipo-news",
    "market"
}

FIELDNAMES = ["Source", "Headline", "Link", "Category", "Time"]

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def filter_categories(category_string):
    cats = category_string.split(",")
    valid = [c for c in cats if c in VALID_CATEGORIES]
    return ",".join(valid)

def parse_categories(class_list):
    return ",".join(
        [cls.split("category-")[1] for cls in class_list if cls.startswith("category-")]
    )

def parse_article_div1(article):
    raw_categories = parse_categories(article.get("class", []))
    filtered_categories = filter_categories(raw_categories)
    if not filtered_categories:
        return None

    headline_tag = article.find("div", class_="entry-title")
    headline = headline_tag.get_text(strip=True) if headline_tag else ""
    link = headline_tag.find("a")["href"] if headline_tag and headline_tag.find("a") else ""
    return {
        "Source": SOURCE,
        "Headline": headline,
        "Link": link,
        "Category": filtered_categories,
        "Time": ""
    }

def parse_article_div2(article):
    raw_categories = parse_categories(article.get("class", []))
    filtered_categories = filter_categories(raw_categories)
    if not filtered_categories:
        return None, None

    title_tag = article.find("div", class_="entry-title")
    headline = title_tag.get_text(strip=True) if title_tag else ""
    link = title_tag.find("a")["href"] if title_tag and title_tag.find("a") else ""
    time_tag = article.find("time")
    timestr = ""
    art_datetime = None
    if time_tag and time_tag.has_attr("datetime"):
        timestr = time_tag["datetime"]
        try:
            art_datetime = datetime.fromisoformat(timestr).astimezone(timezone.utc)
        except ValueError:
            art_datetime = None
    return {
        "Source": SOURCE,
        "Headline": headline,
        "Link": link,
        "Category": filtered_categories,
        "Time": timestr
    }, art_datetime

def get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")

# ----------------------------------------------------------------------------
# CSV Operations
# ----------------------------------------------------------------------------
def load_existing_links():
    links = set()
    if not os.path.exists(CSV_FILE):
        return links
    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                links.add(row["Link"])
    return links

def write_new_records_on_top(new_records):
    existing_records = []
    if os.path.exists(CSV_FILE):
        with FileLock(LOCK_FILE):
            with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_records = list(reader)

    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(new_records)
            writer.writerows(existing_records)

# ----------------------------------------------------------------------------
# Main Scrape
# ----------------------------------------------------------------------------
def scrape():
    page = 1
    stop_scraping = False
    all_new_records = []

    existing_links = load_existing_links()

    while not stop_scraping:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        try:
            soup = get_soup(url)
        except Exception:
            break

        story_divs = soup.find_all("div", class_="wp-block-newspack-blocks-ie-stories")
        if len(story_divs) < 2:
            break

        # div 1
        first_div = story_divs[0]
        first_article = first_div.find("article")
        if first_article:
            record = parse_article_div1(first_article)
            if record:
                if record["Link"] in existing_links:
                    stop_scraping = True
                    break
                all_new_records.append(record)

        # div 2
        second_div = story_divs[1]
        articles = second_div.find_all("article")
        for art in articles:
            record, art_time = parse_article_div2(art)
            if not record:
                continue
            if record["Link"] in existing_links:
                stop_scraping = True
                break

            all_new_records.append(record)

            if art_time and art_time < TIME_LIMIT:
                stop_scraping = True
                break

        if stop_scraping:
            break

        page += 1
        time.sleep(1)

    if all_new_records:
        write_new_records_on_top(all_new_records)
        print(f"... {len(all_new_records)} articles added from FinancialExpress ...")
    else:
        print("... No new FinancialExpress articles found ...")

# ----------------------------------------------------------------------------
# Fix Times
# ----------------------------------------------------------------------------
def fetch_time_from_article_page(link):
    try:
        soup = get_soup(link)
        written_box = soup.find("div", class_="written_box")
        if written_box:
            time_tag = written_box.find("time")
            if time_tag and time_tag.has_attr("datetime"):
                timestr = time_tag["datetime"]
                art_datetime = datetime.fromisoformat(timestr).astimezone(timezone.utc)
                return timestr, art_datetime
    except Exception:
        pass
    return "", None

def fix_csv_times():
    updated_records = []
    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            records = list(reader)

    for row in records:
        if row["Source"] != SOURCE:
            updated_records.append(row)
            continue

        filtered = filter_categories(row["Category"])
        if not filtered:
            continue
        row["Category"] = filtered

        if row["Time"].strip() == "":
            link = row["Link"]
            timestr, art_datetime = fetch_time_from_article_page(link)
            if art_datetime and art_datetime >= TIME_LIMIT:
                row["Time"] = timestr
                updated_records.append(row)
        else:
            try:
                art_datetime = datetime.fromisoformat(row["Time"]).astimezone(timezone.utc)
                if art_datetime >= TIME_LIMIT:
                    updated_records.append(row)
            except Exception:
                continue

    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(updated_records)

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    scrape()
    fix_csv_times()
