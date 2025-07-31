import csv
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import msvcrt

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# === Settings ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
SOURCE = "Economic Times"
TIME_LIMIT = datetime.now(timezone.utc) - timedelta(hours=24)
HEADERS = ["Source", "Headline", "Link", "Category", "Time"]

START_URL = "https://economictimes.indiatimes.com/news/latest-news"

ALLOWED_CATEGORIES = {"markets", "stocks", "ipos", "economy", "finance"}

# === Windows File Locking ===
_locked_sizes = {}

def lock_file(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    if size == 0:
        size = 4096
    file.seek(0)
    msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, size)
    _locked_sizes[file.fileno()] = size

def unlock_file(file):
    size = _locked_sizes.get(file.fileno(), 4096)
    file.seek(0)
    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, size)
    _locked_sizes.pop(file.fileno(), None)

# === Category Parsing ===
def parse_category_from_link(link):
    try:
        path = urlparse(link).path
        parts = path.strip("/").split("/")

        # Remove trailing article identifier
        if parts and "articleshow" in parts[-1]:
            parts = parts[:-1]

        if not parts:
            return ""

        parts = [part.lower() for part in parts]

        # Priority-based category extraction
        if "economy" in parts:
            return "economy"
        if "finance" in parts:
            return "finance"
        if "ipos" in parts:
            return "ipos"
        if len(parts) >= 2 and parts[0] == "markets" and parts[1] == "stocks":
            return "stocks"
        if "markets" in parts:
            return "markets"

        return parts[0]
    except Exception:
        return ""

def is_allowed_category(category):
    return category in ALLOWED_CATEGORIES

# === CSV Handling ===
def read_existing_links():
    links = set()
    if not os.path.exists(CSV_FILE):
        return links
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        lock_file(f)
        reader = csv.DictReader(f)
        for row in reader:
            links.add(row["Link"])
        unlock_file(f)
    return links

def append_new_articles(new_records):
    existing_records = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            lock_file(f)
            reader = csv.DictReader(f)
            existing_records = list(reader)
            unlock_file(f)

    with open(CSV_FILE, 'w+', newline='', encoding='utf-8') as f:
        lock_file(f)
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(new_records)         # new on top
        writer.writerows(existing_records)    # old below
        f.flush()
        unlock_file(f)

# === HTML Parsing ===
def extract_articles_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    ul_data = soup.find("ul", class_="data")
    if not ul_data:
        return []
    return ul_data.find_all("li", recursive=False)

def parse_article_li(li_tag):
    try:
        a_tag = li_tag.find("a", href=True)
        if not a_tag:
            return None, None

        headline = a_tag.get_text(strip=True)
        link = a_tag["href"]
        if not link.startswith("http"):
            link = "https://economictimes.indiatimes.com" + link

        category = parse_category_from_link(link)

        time_tag = li_tag.find("span", class_="timestamp")
        timestr = time_tag["data-time"] if time_tag and time_tag.has_attr("data-time") else ""

        art_datetime = None
        if timestr:
            try:
                art_datetime = datetime.fromisoformat(timestr.replace("Z", "+00:00"))
                art_datetime = art_datetime.astimezone(timezone.utc)
            except ValueError:
                art_datetime = None

        return {
            "Source": SOURCE,
            "Headline": headline,
            "Link": link,
            "Category": category,
            "Time": timestr
        }, art_datetime
    except Exception:
        return None, None

# === Main Scraping ===
def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(START_URL)
    time.sleep(3)

    existing_links = read_existing_links()

    all_new_records = []
    stop_scraping = False
    seen_links = set()

    SCROLL_AMOUNT = 300
    SCROLL_WAIT = 1.0
    MAX_SCROLLS = 100

    scroll_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")

    while not stop_scraping and scroll_count < MAX_SCROLLS:
        driver.execute_script(f"window.scrollBy(0, {SCROLL_AMOUNT});")
        time.sleep(SCROLL_WAIT)

        page_source = driver.page_source
        articles = extract_articles_from_html(page_source)

        for li in articles:
            record, art_time = parse_article_li(li)
            if not record:
                continue

            if record["Link"] in existing_links or record["Link"] in seen_links:
                stop_scraping = True
                break

            if art_time and art_time < TIME_LIMIT:
                stop_scraping = True
                break

            if not is_allowed_category(record["Category"]):
                continue

            all_new_records.append(record)
            seen_links.add(record["Link"])

        if stop_scraping:
            break

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_count += 1

    driver.quit()

    if all_new_records:
        append_new_articles(all_new_records)

if __name__ == "__main__":
    main()
