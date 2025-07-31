import csv
import os
import sys
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from filelock import FileLock

# === Settings ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = CSV_FILE + ".lock"
SOURCE = "Investing.com"
HEADERS = ["Source", "Headline", "Link", "Category", "Time"]
START_URL = "https://www.investing.com/news/latest-news"
WAIT_TIMEOUT = 20

def parse_category_from_link(link):
    try:
        path = urlparse(link).path
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            category_part = parts[1]
            if "-" in category_part:
                return category_part.split("-")[0]
            return category_part
    except Exception:
        pass
    return ""

def read_existing_links():
    links = set()
    if not os.path.exists(CSV_FILE):
        return links
    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                links.add(row["Link"])
    return links

def append_new_articles(new_records):
    existing_records = []
    if os.path.exists(CSV_FILE):
        with FileLock(LOCK_FILE):
            with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_records = list(reader)
    with FileLock(LOCK_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(new_records)
            writer.writerows(existing_records)

def extract_articles_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article", attrs={"data-test": "article-item"})
    records = []
    for article in articles:
        a_tag = article.find("a", attrs={"data-test": "article-title-link"})
        if not a_tag:
            continue
        headline = a_tag.get_text(strip=True)
        link = a_tag["href"]
        if not link.startswith("http"):
            link = "https://www.investing.com" + link
        category = parse_category_from_link(link)
        time_tag = article.find("time", attrs={"data-test": "article-publish-date"})
        timestr = time_tag["datetime"] if time_tag and time_tag.has_attr("datetime") else ""
        records.append({
            "Source": SOURCE,
            "Headline": headline,
            "Link": link,
            "Category": category,
            "Time": timestr
        })
    return records

def main():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.page_load_strategy = "none"  # Don't wait for full load!

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = None
    ul_html = None

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(WAIT_TIMEOUT)
        
        print(f"Opening {START_URL} ...")
        driver.get(START_URL)

        # Let initial stuff load
        time.sleep(5)
        driver.execute_script("window.stop();")  # Cancel any long-loading junk

        # Now wait just for our target element
        WebDriverWait(driver, WAIT_TIMEOUT, poll_frequency=1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul[data-test='news-list']"))
        )
        ul_element = driver.find_element(By.CSS_SELECTOR, "ul[data-test='news-list']")
        ul_html = ul_element.get_attribute('outerHTML')

    except TimeoutException:
        print(f"ERROR: Timeout waiting for Investing.com page or elements.")
        sys.exit(1)

    except Exception as e:
        print(f"ERROR: Problem loading Investing.com page: {e}")
        sys.exit(1)

    finally:
        if driver:
            driver.quit()

    if not ul_html:
        print("WARNING: Could not retrieve page content.")
        return

    existing_links = read_existing_links()
    all_new_records = []

    articles = extract_articles_from_html(ul_html)
    for record in articles:
        if record["Link"] in existing_links:
            continue
        all_new_records.append(record)

    if all_new_records:
        append_new_articles(all_new_records)
        print(f"{len(all_new_records)} new articles added from Investing.com.")
    else:
        print("No new Investing.com articles found.")

if __name__ == "__main__":
    main()
