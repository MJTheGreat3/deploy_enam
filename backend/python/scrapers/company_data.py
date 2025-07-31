import os
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import concurrent.futures
from datetime import datetime
from .common import (
    log_debug, get_csv_path, append_unique_rows,
    check_system_resources, load_portfolio_symbols,
    remove_duplicates_from_csv_with_header, convert_nse_datetime
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_PORTFOLIO_CSV = os.path.abspath(os.path.join(SCRIPT_DIR, "../../user_portfolio.csv"))

INSIDER_HEADERS = [
    "Stock", "Clause", "Name", "Type", "Amount", "Value", "Transaction", "Attachment", "Time"
]

ANNOUNCEMENTS_HEADERS = [
    "Stock", "Subject", "Announcement", "Attachment", "Time"
]

def create_driver():
    options = Options()
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--incognito")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver

def scrape_company_data(company):
    for attempt in range(3):
        driver = None
        try:
            print(f"Starting scrape for: {company}")
            check_system_resources()
            driver = create_driver()
            driver.get(f"https://www.nseindia.com/get-quotes/equity?symbol={company}")
            wait = WebDriverWait(driver, 20)

            # ANNOUNCEMENTS
            try:
                ann_button = wait.until(EC.presence_of_element_located((By.ID, "announcements")))
                if not ann_button.is_displayed():
                    raise Exception("Announcements tab hidden or absent")

                driver.execute_script("arguments[0].scrollIntoView(true);", ann_button)
                wait.until(EC.element_to_be_clickable((By.ID, "announcements")))
                driver.execute_script("arguments[0].click();", ann_button)
                time.sleep(1)

                try:
                    ten_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-val="6M"]')))
                    driver.execute_script("arguments[0].click();", ten_button)
                    time.sleep(1)
                except Exception:
                    print(f"[{company}] Could not select 6M filter")

                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#corpAnnouncementTable tbody')))
                readmores = driver.find_elements(By.CSS_SELECTOR, 'a.readMore')
                for link in readmores:
                    try:
                        driver.execute_script("arguments[0].click();", link)
                        time.sleep(0.2)
                    except:
                        continue

                soup = BeautifulSoup(driver.page_source, "html.parser")
                div = soup.find('div', id="corpAnnouncementTable")
                anns = []
                if div and div.find('tbody'):
                    for row in div.find('tbody').find_all('tr'):
                        tds = row.find_all("td")
                        if len(tds) < 4:
                            continue
                        ann = [company]
                        ann.append(tds[0].get_text(strip=True))
                        span = tds[1].find("span")
                        ann.append(span.get_text(strip=True) if span else tds[1].get_text(strip=True))
                        a_tag = tds[2].find("a")
                        ann.append(a_tag.get("href") if a_tag else None)
                        for d in tds[3].find_all("div"):
                            d.extract()
                        time_val = tds[3].get_text(strip=True)
                        ann.append(convert_nse_datetime(time_val))
                        anns.append(ann)

                    if anns:
                        append_unique_rows("announcements.csv", anns, header=ANNOUNCEMENTS_HEADERS)
                        print(f"[{company}] Announcements extracted: {len(anns)} records")
                    else:
                        print(f"[{company}] No announcements found")
                else:
                    print(f"[{company}] Announcements table missing")
            except Exception as e:
                print(f"[{company}] Announcements error: {str(e)[:150]}")

            # INSIDER TRADING
            try:
                it_button = wait.until(EC.presence_of_element_located((By.ID, "insiderTrading")))
                if not it_button.is_displayed():
                    raise Exception("Insider Trading tab hidden or absent")

                driver.execute_script("arguments[0].scrollIntoView(true);", it_button)
                wait.until(EC.element_to_be_clickable((By.ID, "insiderTrading")))
                driver.execute_script("arguments[0].click();", it_button)
                time.sleep(2)

                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#corpInsiderTradingTable tbody')))
                soup = BeautifulSoup(driver.page_source, "html.parser")
                div = soup.find('div', id="corpInsiderTradingTable")
                its = []
                if div and div.find('tbody'):
                    for row in div.find('tbody').find_all('tr'):
                        tds = row.find_all('td')
                        if len(tds) != 8:
                            continue
                        it = [company]
                        for n in range(8):
                            if n == 6 and tds[n].find('a'):
                                it.append(tds[n].find('a').get("href"))
                            elif n == 7:
                                it.append(convert_nse_datetime(tds[n].get_text(strip=True)))
                            else:
                                it.append(tds[n].get_text(strip=True))
                        its.append(it)

                    if its:
                        append_unique_rows("insider_trading.csv", its, header=INSIDER_HEADERS)
                        print(f"[{company}] Insider Trading extracted: {len(its)} records")
                    else:
                        print(f"[{company}] No insider trading data found")
                else:
                    print(f"[{company}] Insider Trading table missing")
            except Exception as e:
                print(f"[{company}] Insider Trading error: {str(e)[:150]}")
            return
        except Exception as e:
            print(f"{company} attempt {attempt+1}/3 failed: {str(e)[:100]}")
            time.sleep(2 ** attempt)
        finally:
            if driver:
                driver.quit()

def run_company_scrapers(only_new=False):
    start_time = time.time()
    companies = load_portfolio_symbols(only_new=only_new)
    if not companies:
        print("[WARN] No companies in portfolio, skipping company scraping")
        return

    tasks = [lambda c=c: scrape_company_data(c) for c in companies]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except:
                pass

    for filename in ["announcements.csv", "insider_trading.csv"]:
        full_path = get_csv_path(filename)
        if os.path.exists(full_path):
            remove_duplicates_from_csv_with_header(full_path)

    if only_new:
        if os.path.exists(USER_PORTFOLIO_CSV):
            df = pd.read_csv(USER_PORTFOLIO_CSV)
            if 'status' in df.columns:
                df.loc[df['status'].str.upper() == "NEW", 'status'] = "Old"
                df.to_csv(USER_PORTFOLIO_CSV, index=False)

    print(f"Company scraping completed in {time.time()-start_time:.2f} seconds")
