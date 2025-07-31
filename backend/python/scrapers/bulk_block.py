import os
import time
import re
import requests
import traceback
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import concurrent.futures
from .common import log_debug, get_csv_path, append_unique_rows, check_system_resources, remove_duplicates_from_csv_with_header

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
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver

def scrape_bse_bulk():
    for attempt in range(3):
        try:
            check_system_resources()
            driver = create_driver()
            bulk_url = "https://www.bseindia.com/markets/equity/EQReports/bulk_deals.aspx"
            driver.get(bulk_url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span[name*='notedate']"))
            )
            soup = BeautifulSoup(driver.page_source, "html.parser")
            date_string = soup.find('span', attrs={'name': re.compile(r'notedate')}).get_text(strip=True)
            table = soup.find('table', attrs={'name': re.compile(r'bulkdeals')})
            bulks = []
            body = table.find('tbody')
            rows = body.find_all('tr')
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all('td')]
                if len(cells) >= 1:
                    if cells[4] == "B":
                        cells[4] = "BUY"
                    elif cells[4] == "S":
                        cells[4] = "SELL"
                    bulks.append(["BSE"] + [cells[0]] + cells[2:])
            append_unique_rows("bulk_deals.csv", bulks)
            print(f"BSE Bulk Deals extracted ({date_string})")
            return
        except Exception as e:
            print(f"BSE Bulk attempt {attempt+1}/3 failed: {str(e)[:100]}")
            time.sleep(2 ** attempt)
        finally:
            try:
                driver.quit()
            except:
                pass

def scrape_bse_block():
    for attempt in range(3):
        try:
            check_system_resources()
            driver = create_driver()
            block_bse_url = "https://www.bseindia.com/markets/equity/EQReports/block_deals.aspx"
            driver.get(block_bse_url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span[name*='note']"))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            date_string = soup.find('span', attrs={'name': re.compile(r'note')}).get_text(strip=True)
            table = soup.find('table', attrs={'name': re.compile(r'block')})
            bse_blocks = []
            body = table.find('tbody')
            rows = body.find_all('tr')
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all('td')]
                if len(cells) >= 1:
                    if cells[4] == "B":
                        cells[4] = "Buy"
                    elif cells[4] == "S":
                        cells[4] = "Sell"
                    bse_blocks.append(["BSE"] + [cells[0]] + cells[2:])
            append_unique_rows("block_deals.csv", bse_blocks)
            print(f"BSE Block Deals extracted ({date_string})")
            return
        except Exception as e:
            print(f"BSE Block attempt {attempt+1}/3 failed: {str(e)[:100]}")
            time.sleep(2 ** attempt)
        finally:
            try:
                driver.quit()
            except:
                pass

def scrape_nse_bulk():
    for attempt in range(3):
        try:
            check_system_resources()
            today = datetime.today()
            to_date = today.strftime("%d-%m-%Y")
            from_date = (today - timedelta(days=30)).strftime("%d-%m-%Y")

            log_debug(f"[NSE BULK] Attempt {attempt+1}: from={from_date} to={to_date}")

            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en;q=0.5',
                'priority': 'u=1, i',
                'referer': 'https://www.nseindia.com/report-detail/display-bulk-and-block-deals',
                'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0'
            }
            params = {
                'optionType': 'bulk_deals',
                'from': from_date,
                'to': to_date,
            }

            session = requests.Session()
            homepage_resp = session.get('https://www.nseindia.com/', headers=headers, timeout=10)
            log_debug(f"[NSE BULK] Homepage GET status={homepage_resp.status_code}")

            response = session.get(
                'https://www.nseindia.com/api/historicalOR/bulk-block-short-deals',
                params=params,
                headers=headers,
                timeout=15
            )
            log_debug(f"[NSE BULK] API GET status={response.status_code}")

            response.raise_for_status()

            try:
                data = response.json()
                log_debug(f"[NSE BULK] Response JSON keys: {list(data.keys())}")
            except Exception as je:
                log_debug(f"[NSE BULK] JSON decode error: {je}")
                log_debug(f"[NSE BULK] Raw response text:\n{response.text}")
                raise

            nse_bulk = []
            for record in data.get('data', []):
                original_date = record['BD_DT_DATE']
                dt = datetime.strptime(original_date, "%d-%b-%Y")
                formatted_date = dt.strftime("%d/%m/%Y")
                nse_bulk.append([
                    'NSE',
                    formatted_date,
                    record['BD_SYMBOL'],
                    record['BD_CLIENT_NAME'],
                    record['BD_BUY_SELL'],
                    record['BD_QTY_TRD'],
                    record['BD_TP_WATP']
                ])
            append_unique_rows("bulk_deals.csv", nse_bulk)
            print(f"NSE Bulk Deals extracted")
            return
        except Exception as e:
            log_debug(f"[NSE BULK] Exception:\n{traceback.format_exc()}")
            print(f"NSE Bulk attempt {attempt+1}/3 failed: {str(e)[:100]}")
            time.sleep(2 ** attempt)

def scrape_nse_block():
    for attempt in range(3):
        try:
            check_system_resources()
            today = datetime.today()
            to_date = today.strftime("%d-%m-%Y")
            from_date = (today - timedelta(days=30)).strftime("%d-%m-%Y")

            log_debug(f"[NSE BLOCK] Attempt {attempt+1}: from={from_date} to={to_date}")

            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en;q=0.5',
                'priority': 'u=1, i',
                'referer': 'https://www.nseindia.com/report-detail/display-bulk-and-block-deals',
                'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0'
            }
            params = {
                'optionType': 'block_deals',
                'from': from_date,
                'to': to_date,
            }

            session = requests.Session()
            homepage_resp = session.get('https://www.nseindia.com/', headers=headers, timeout=10)
            log_debug(f"[NSE BLOCK] Homepage GET status={homepage_resp.status_code}")

            response = session.get(
                'https://www.nseindia.com/api/historicalOR/bulk-block-short-deals',
                params=params,
                headers=headers,
                timeout=15
            )
            log_debug(f"[NSE BLOCK] API GET status={response.status_code}")

            response.raise_for_status()

            try:
                data = response.json()
                log_debug(f"[NSE BLOCK] Response JSON keys: {list(data.keys())}")
            except Exception as je:
                log_debug(f"[NSE BLOCK] JSON decode error: {je}")
                log_debug(f"[NSE BLOCK] Raw response text:\n{response.text}")
                raise

            nse_block = []
            for record in data.get('data', []):
                original_date = record['BD_DT_DATE']
                dt = datetime.strptime(original_date, "%d-%b-%Y")
                formatted_date = dt.strftime("%d/%m/%Y")
                nse_block.append([
                    'NSE',
                    formatted_date,
                    record['BD_SYMBOL'],
                    record['BD_CLIENT_NAME'],
                    record['BD_BUY_SELL'],
                    record['BD_QTY_TRD'],
                    record['BD_TP_WATP']
                ])
            append_unique_rows("block_deals.csv", nse_block)
            print(f"NSE Block Deals extracted")
            return
        except Exception as e:
            log_debug(f"[NSE BLOCK] Exception:\n{traceback.format_exc()}")
            print(f"NSE Block attempt {attempt+1}/3 failed: {str(e)[:100]}")
            time.sleep(2 ** attempt)

def run_bulk_block_scrapers():
    start_time = time.time()
    tasks = [
        scrape_bse_bulk,
        scrape_bse_block,
        scrape_nse_bulk,
        scrape_nse_block
    ]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except:
                pass
    
    for filename in ["bulk_deals.csv", "block_deals.csv"]:
        full_path = get_csv_path(filename)
        if os.path.exists(full_path):
            remove_duplicates_from_csv_with_header(full_path)
    
    print(f"Bulk/Block scraping completed in {time.time()-start_time:.2f} seconds")