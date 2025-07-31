import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from threading import Lock
import sys
import os
from collections import deque
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Aggressive but safe rate limiting
class AggressiveRateLimiter:
    def __init__(self, max_requests_per_minute=25, burst_size=8):
        self.max_requests_per_minute = max_requests_per_minute
        self.burst_size = burst_size
        self.request_times = deque()
        self.lock = Lock()
        
    def wait_if_needed(self):
        """Aggressive but smart rate limiting"""
        with self.lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            
            # Check if we're at burst limit (short term)
            recent_requests = [t for t in self.request_times if now - t < 10]  # Last 10 seconds
            if len(recent_requests) >= self.burst_size:
                sleep_time = 2.0
                time.sleep(sleep_time)
            
            # Check if we're at rate limit (long term)
            elif len(self.request_times) >= self.max_requests_per_minute:
                sleep_time = 60 - (now - self.request_times[0]) + 1
                logger.warning(f"⏳ Rate limit reached. Brief pause: {sleep_time:.1f}s")
                time.sleep(min(sleep_time, 10))  # Cap at 10 seconds
            
            # Record this request
            self.request_times.append(now)

# Global rate limiter
rate_limiter = AggressiveRateLimiter(max_requests_per_minute=25, burst_size=8)

def clean_ticker_for_screener(ticker):
    """Clean ticker symbol for screener.in URL"""
    return re.sub(r'[^A-Z0-9]', '', ticker.upper().replace('.NS', '').replace('.BO', ''))

def parse_market_cap(market_cap_text):
    """Parse market cap text and convert to numeric value in crores"""
    if not market_cap_text or market_cap_text == 'Not Available':
        return None
    
    try:
        # Remove commas, spaces, and currency symbols
        market_cap_text = market_cap_text.replace(',', '').replace(' ', '').replace('₹', '').replace('Rs', '').upper()
        
        # Extract numeric part and unit
        match = re.search(r'([\d.]+)([A-Z]*)', market_cap_text)
        if not match:
            return None
        
        value = float(match.group(1))
        unit = match.group(2)
        
        # Convert to crores
        if 'LAKH' in unit:
            return value / 100
        elif 'CRORE' in unit or 'CR' in unit:
            return value
        elif 'THOUSAND' in unit:
            return value / 10000
        else:
            return value
    except:
        return None

def get_market_cap_fast(symbol):
    """Fast market cap retrieval with minimal delays"""
    # Wait for rate limiting
    rate_limiter.wait_if_needed()
    
    try:
        clean_symbol = clean_ticker_for_screener(symbol)
        url = f"https://www.screener.in/company/{clean_symbol}/consolidated/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Minimal delay - let rate limiter handle the timing
        time.sleep(random.uniform(0.5, 1.2))
        
        response = requests.get(url, headers=headers, timeout=12)
        
        if response.status_code == 429:
            # Quick exponential backoff
            time.sleep(random.uniform(8, 12))
            response = requests.get(url, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Fast extraction - prioritize most common locations
        market_cap = None
        
        # Method 1: Top ratios (most reliable)
        top_ratios = soup.find('ul', id='top-ratios')
        if top_ratios:
            for li in top_ratios.find_all('li', class_='flex flex-space-between'):
                text = li.get_text(strip=True)
                if 'Market Cap' in text:
                    match = re.search(r'₹[^0-9]*[\d,]+(?:\.\d+)?\s*(?:Cr\.?|Crore)', text)
                    if match:
                        market_cap = parse_market_cap(match.group())
                        if market_cap:
                            break
        
        # Method 2: Quick text search if method 1 fails
        if not market_cap:
            text_content = soup.get_text()
            matches = re.findall(r'Market Cap[^₹]*₹[^0-9]*[\d,]+(?:\.\d+)?\s*Cr\.?', text_content)
            if matches:
                market_cap = parse_market_cap(matches[0])
        
        if market_cap:
            return market_cap
        else:
            return None
            
    except Exception as e:
        return None

def process_company_fast(row):
    """Fast company processing"""
    try:
        company = row['Company']
        
        # Try both .NS and without extension
        market_cap = get_market_cap_fast(f"{company}.NS")
        if not market_cap:
            market_cap = get_market_cap_fast(company)
        
        # Create result with all original columns plus market cap
        result = row.to_dict()
        result['Market Cap (Cr)'] = market_cap
        
        if market_cap:
            logger.info(f"✅ {company}: ₹{market_cap:,.0f} Cr")
        else:
            logger.warning(f"⚠️ {company}: Market Cap not found")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error processing {row.get('Company', 'Unknown')}: {e}")
        result = row.to_dict()
        result['Market Cap (Cr)'] = None
        return result

def add_market_cap_classification(df):
    """Add market cap classification column"""
    def classify_market_cap(market_cap):
        if pd.isna(market_cap):
            return "Unknown"
        elif market_cap >= 20000:
            return "Large Cap"
        elif market_cap >= 5000:
            return "Mid Cap"
        else:
            return "Small Cap"
    
    df['Market Cap Category'] = df['Market Cap (Cr)'].apply(classify_market_cap)
    return df

def find_input_file(target_date=None):
    """Find the correct input file, with or without date parameter"""
    
    # If date is provided, try the date-specific filename first
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d_%m_%Y')
            date_specific_file = f"Enhanced_ATH_Analysis_with_threshold_{formatted_date}.csv"
            
            if os.path.exists(date_specific_file):
                print(f"✅ Found date-specific file: {date_specific_file}")
                return date_specific_file
            else:
                print(f"⚠️ Date-specific file not found: {date_specific_file}")
                
        except ValueError:
            print(f"❌ Invalid date format: {target_date}")
    
    # Fallback options - try common filenames
    fallback_files = [
        "Enhanced_ATH_Analysis_with_thresholds.csv",  # Your old working filename
        "Enhanced_ATH_Analysis_with_threshold.csv",
        "Enhanced_ATH_Analysis.csv"
    ]
    
    for filename in fallback_files:
        if os.path.exists(filename):
            print(f"✅ Found fallback file: {filename}")
            return filename
    
    # If nothing found, list available CSV files
    print("❌ No suitable input file found!")
    print("📂 Available CSV files:")
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'Enhanced' in f]
    for f in csv_files:
        print(f"   📄 {f}")
    
    return None

def main():
    """Main function with flexible date handling"""
    
    print("🚀 ULTRA-FAST ATH Analysis with Market Cap Integration")
    print("=" * 70)
    
    # Handle command line arguments
    target_date = None
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        print(f"📅 Target date provided: {target_date}")
    else:
        print("📅 No date provided, using fallback file search")
    
    # Find the input file
    input_file = find_input_file(target_date)
    if not input_file:
        print("❌ Cannot proceed without input file!")
        sys.exit(1)
    
    # Load Enhanced ATH analysis data
    try:
        ath_df = pd.read_csv(input_file)
        logger.info(f"📊 Loaded {len(ath_df)} companies from {input_file}")
        
        # Debug: Print column names to verify
        logger.info(f"📋 Columns found: {list(ath_df.columns)}")
        
        # Show first few companies for verification
        if len(ath_df) > 0:
            print(f"🔍 First 3 companies: {ath_df['Company'].head(3).tolist()}")
        
    except Exception as e:
        logger.error(f"❌ Error loading file {input_file}: {e}")
        sys.exit(1)
    
    start_time = time.time()
    
    logger.info(f"🚀 Processing {len(ath_df)} companies with 4 threads...")
    
    results = []
    
    # More aggressive threading
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks
        future_to_company = {
            executor.submit(process_company_fast, row): row['Company'] 
            for _, row in ath_df.iterrows()
        }
        
        completed = 0
        total = len(future_to_company)
        
        # Process results as they complete
        for future in as_completed(future_to_company):
            company_name = future_to_company[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1
                
                # Progress updates every 25 companies
                if completed % 25 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 and completed < total else 0
                    
                    logger.info(f"🔄 Progress: {completed}/{total} ({completed/total*100:.1f}%) - "
                              f"Rate: {rate*60:.1f}/min - ETA: {eta/60:.1f}min")
                
            except Exception as e:
                logger.error(f"❌ Failed {company_name}: {e}")
                # Add failed result
                try:
                    failed_row = ath_df[ath_df['Company'] == company_name].iloc[0]
                    result = failed_row.to_dict()
                    result['Market Cap (Cr)'] = None
                    results.append(result)
                except:
                    pass
    
    # Create final DataFrame
    final_df = pd.DataFrame(results)
    
    # Add market cap classification
    final_df = add_market_cap_classification(final_df)
    
    # Sort by Category first, then by Market Cap
    final_df = final_df.sort_values(['Category', 'Market Cap (Cr)'], 
                                    ascending=[True, False], 
                                    na_position='last')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_dir = os.path.join(base_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    
    # Generate output filenames based on date
    if target_date:
     try:
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d_%m_%Y')
        main_output_file = f"ATH_companies_with_market_cap_{formatted_date}.csv"
     except:
        main_output_file = "ATH_companies_with_market_cap.csv"
    else:
     main_output_file = "ATH_companies_with_market_cap.csv"

    # Full path in /csv/
     output_path = os.path.join(csv_dir, main_output_file)

    # Save results
    final_df.to_csv(output_path, index=False)
    # Quick statistics
    valid_market_caps = final_df['Market Cap (Cr)'].dropna()
    total_time = time.time() - start_time
    
    print("\n" + "="*70)
    logger.info("🎉 ULTRA-FAST PROCESSING COMPLETE!")
    logger.info("=" * 50)
    logger.info(f"⏱️ Total time: {total_time/60:.1f} minutes")
    logger.info(f"⚡ Processing rate: {len(final_df)/(total_time/60):.1f} companies/minute")
    logger.info(f"📊 Success rate: {len(valid_market_caps)/len(final_df)*100:.1f}%")
    logger.info(f"✅ Companies with data: {len(valid_market_caps)}")
    logger.info(f"❌ Companies without data: {len(final_df) - len(valid_market_caps)}")
    
    if len(valid_market_caps) > 5:
        logger.info(f"\n💰 Market Cap Summary:")
        logger.info(f"Largest: ₹{valid_market_caps.max():,.0f} Cr")
        logger.info(f"Smallest: ₹{valid_market_caps.min():,.0f} Cr")
        logger.info(f"Average: ₹{valid_market_caps.mean():,.0f} Cr")
        
        # Quick distribution
        large_cap = (valid_market_caps >= 20000).sum()
        mid_cap = ((valid_market_caps >= 5000) & (valid_market_caps < 20000)).sum()
        small_cap = (valid_market_caps < 5000).sum()
        
        logger.info(f"\n📈 Distribution:")
        logger.info(f"Large Cap (>₹20k Cr): {large_cap}")
        logger.info(f"Mid Cap (₹5k-20k Cr): {mid_cap}")
        logger.info(f"Small Cap (<₹5k Cr): {small_cap}")
    
    # Generate category files with date-specific names if applicable
    for category in [0, 5, 10]:
        category_data = final_df[final_df['Category'] == category]
        if not category_data.empty:
            category_name = "New_ATH" if category == 0 else f"Within_{category}_Percent_ATH"
            
            if target_date:
                try:
                    date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d_%m_%Y')
                    filename = f"{category_name}_with_market_cap_{formatted_date}.csv"
                except:
                    filename = f"{category_name}_with_market_cap.csv"
            else:
                filename = f"{category_name}_with_market_cap.csv"
                
            category_data.to_csv(filename, index=False)
            logger.info(f"📁 Created: {filename}")
    
    logger.info(f"\n📁 Main results: {main_output_file}")
    logger.info(f"🎯 Average time per company: {(total_time/len(final_df)):.1f} seconds")
    
    if target_date:
        logger.info(f"📅 Analysis completed for date: {target_date}")

if __name__ == "__main__":
    main()