from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import pandas as pd
from datetime import datetime
import os
from filelock import FileLock

URL = "https://www.cnbctv18.com/latest-news/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))
LOCK_FILE = CSV_FILE + ".lock"
SOURCE_NAME = "CNBC TV 18"

COLUMNS = ["Source", "Headline", "Link", "Category", "Time"]
ALLOWED_CATEGORIES = {"market", "stock", "business", "economy"}

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

def load_existing_links():
    with FileLock(LOCK_FILE):
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            if not all(col in df.columns for col in COLUMNS):
                df = pd.DataFrame(columns=COLUMNS)
                df.to_csv(CSV_FILE, index=False)
            return set(df["Link"].dropna().tolist())
        else:
            return set()

existing_links = load_existing_links()

def is_today(date_str):
    try:
        article_date = datetime.strptime(date_str.strip(), "%b %d, %Y %I:%M %p")
        return article_date.date() == datetime.now().date()
    except Exception:
        return False

def extract_articles(soup, existing_links):
    articles = soup.find_all("article", class_="story-item")
    extracted = []
    stop_flag = False

    for article in articles:
        try:
            category_tag = article.find("span", class_="story-cat")
            category = category_tag.text.strip().lower() if category_tag else ""
            if category not in ALLOWED_CATEGORIES:
                continue

            title_tag = article.find("h2", class_="story-title")
            title = title_tag.text.strip() if title_tag else ""
            link_tag = title_tag.find_parent("a") if title_tag else None
            link = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""

            time_tag = article.find("time")
            published_time = time_tag.text.strip() if time_tag else ""

            if not is_today(published_time):
                stop_flag = True
                break
            if link in existing_links:
                stop_flag = True
                break

            extracted.append({
                "Source": SOURCE_NAME,
                "Headline": title,
                "Link": link,
                "Category": category,
                "Time": published_time
            })
        except Exception:
            continue

    return extracted, stop_flag

def scroll_and_scrape():
    driver.get(URL)
    time.sleep(3)

    all_articles = []
    stop = False
    last_height = driver.execute_script("return document.body.scrollHeight")
    max_scrolls = 50

    for _ in range(max_scrolls):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        new_articles, stop = extract_articles(soup, existing_links)
        all_articles.extend(new_articles)
        if stop:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()

    if all_articles:
        new_df = pd.DataFrame(all_articles, columns=COLUMNS)
        with FileLock(LOCK_FILE):
            if os.path.exists(CSV_FILE):
                current_df = pd.read_csv(CSV_FILE)
                if not all(col in current_df.columns for col in COLUMNS):
                    current_df = pd.DataFrame(columns=COLUMNS)
                combined_df = pd.concat([new_df, current_df], ignore_index=True)
            else:
                combined_df = new_df

            combined_df.to_csv(CSV_FILE, index=False)

        print(f"{len(all_articles)} articles added from CNBCTV18.")
    else:
        print("0 articles added from CNBCTV18.")

if __name__ == "__main__":
    scroll_and_scrape()
