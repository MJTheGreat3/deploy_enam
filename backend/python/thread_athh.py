import requests
import pandas as pd
from datetime import datetime
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import sys
import os


# === Yahoo Finance Data ===
def get_yahoo_data_direct(symbol, period1, period2):
    # Convert to UNIX timestamps
    if isinstance(period1, str):
        period1 = int(datetime.strptime(period1, "%Y-%m-%d").timestamp())
    elif isinstance(period1, pd.Timestamp):
        period1 = int(period1.timestamp())
    
    if isinstance(period2, str):
        period2 = int(datetime.strptime(period2, "%Y-%m-%d").timestamp())
    elif isinstance(period2, pd.Timestamp):
        period2 = int(period2.timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        'period1': period1,
        'period2': period2,
        'interval': '1d',
        'includePrePost': 'true',
        'events': 'div,split'
    }
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if 'chart' in data and data['chart']['result']:
            result = data['chart']['result'][0]
            timestamps = result['timestamp']
            ohlcv = result['indicators']['quote'][0]
            df = pd.DataFrame({
                'Date': pd.to_datetime(timestamps, unit='s'),
                'Open': ohlcv['open'],
                'High': ohlcv['high'],
                'Low': ohlcv['low'],
                'Close': ohlcv['close'],
                'Volume': ohlcv['volume']
            }).dropna()
            df.set_index('Date', inplace=True)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error fetching Yahoo data for {symbol}: {e}")
        return pd.DataFrame()


# === Enhanced ATH Detection with 5% and 10% thresholds ===
def detect_ath_and_near_ath_since_past_5_years(df, target_end):
    target_end = pd.to_datetime(target_end)
    target_start = target_end - pd.DateOffset(months=1)
    history_start = target_end - pd.DateOffset(years=5)

    history_data = df[(df.index >= history_start) & (df.index < target_start)]
    target_fy_data = df[(df.index >= target_start) & (df.index <= target_end)]

    if history_data.empty or target_fy_data.empty:
        return None, None, None
    
    # Get the ATH from historical data (past 5 years excluding target month)
    historical_ath = history_data['Close'].max()
    
    # Get the highest price during the target month
    target_month_high = target_fy_data['Close'].max()
    target_month_high_date = target_fy_data[target_fy_data['Close'] == target_month_high].index[-1]
    
    # Calculate thresholds
    threshold_5_percent = historical_ath * 0.95  # 5% below ATH
    threshold_10_percent = historical_ath * 0.90  # 10% below ATH
    
    # Check what category the stock falls into
    if target_month_high > historical_ath:
        # New ATH achieved
        return target_month_high_date, 0, target_month_high
    elif target_month_high >= threshold_5_percent:
        # Within 5% of ATH
        return target_month_high_date, 5, target_month_high
    elif target_month_high >= threshold_10_percent:
        # Within 10% of ATH
        return target_month_high_date, 10, target_month_high
    else:
        # Not within 10% of ATH
        return None, None, None


# === Load ticker-sector-industry mapping ===
df_2 = pd.read_excel('../csv/Tickers 1.xlsx')
df_2['Base Symbol'] = df_2['Stock Ticker'].astype(str).str.strip().str.replace('.NS', '', regex=False)
sector_industry_map = df_2.drop_duplicates(subset='Base Symbol').set_index('Base Symbol')[['Sector', 'Industry']].to_dict('index')

# Prepare list of .NS symbols for Yahoo
tickers = df_2['Base Symbol'].astype(str) + ".NS"


# === Per-ticker Thread Task ===
def process_ticker(symbol, period1_dt, period2_dt):
    try:
        df = get_yahoo_data_direct(symbol, period1_dt, period2_dt)
        if df.empty:
            return None, symbol

        peak_date, category, peak_price = detect_ath_and_near_ath_since_past_5_years(df, period2_dt)
        
        if peak_date is not None:
            base_symbol = symbol.replace('.NS', '')

            if base_symbol in sector_industry_map:
                sector = sector_industry_map[base_symbol]['Sector']
                industry = sector_industry_map[base_symbol]['Industry']
            else:
                sector = industry = "Unknown"

            # Determine status description
            if category == 0:
                status = "New ATH"
            elif category == 5:
                status = "Within 5% of ATH"
            elif category == 10:
                status = "Within 10% of ATH"

            return {
                "Company": base_symbol,
                "Peak Date": peak_date.date(),
                "Peak Price": round(peak_price, 2),
                "Status": status,
                "Category": category,
                "Sector": sector,
                "Industry": industry
            }, None
        return None, None
    except Exception as e:
        print(f"⚠️ Error processing {symbol}: {e}")
        return None, symbol


# === Main Process ===
# Get target date from CLI
target_date = None
if len(sys.argv) > 1:
    target_date = sys.argv[1]

# Use passed-in date or fallback to today
if target_date:
    target_fy_end = pd.to_datetime(target_date)
else:
    target_fy_end = pd.to_datetime("today")

period1_dt = target_fy_end - pd.DateOffset(months=1) - pd.DateOffset(years=5)

peak_records = []
skipped = []

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {
        executor.submit(process_ticker, symbol, period1_dt, target_fy_end): symbol
        for symbol in tickers
    }
    for future in as_completed(futures):
        result, skipped_symbol = future.result()
        if result:
            peak_records.append(result)
            print(f"✅ {result['Company']} - {result['Status']} on {result['Peak Date']} (₹{result['Peak Price']})")
        elif skipped_symbol:
            print(f"⛔ No data for {skipped_symbol}")
            skipped.append(skipped_symbol.replace('.NS', ''))

# === Output Results ===
peak_df = pd.DataFrame(peak_records)

# Sort by category (ATH first, then 5%, then 10%)
peak_df = peak_df.sort_values('Category')

# Get target_fy_end date in dd_mm_yyyy format
current_date = target_fy_end.strftime("%d_%m_%Y")

# Save main file with date
main_filename = f"Enhanced_ATH_Analysis_with_threshold_{current_date}.csv"
peak_df.to_csv(main_filename, index=False)

# Generate separate reports for each category
ath_companies = peak_df[peak_df['Category'] == 0]
within_5_percent = peak_df[peak_df['Category'] == 5]
within_10_percent = peak_df[peak_df['Category'] == 10]

if not ath_companies.empty:
    ath_companies.to_csv("New_ATH_Companies.csv", index=False)
if not within_5_percent.empty:
    within_5_percent.to_csv("Within_5_Percent_ATH.csv", index=False)
if not within_10_percent.empty:
    within_10_percent.to_csv("Within_10_Percent_ATH.csv", index=False)

# Generate sector and industry analysis
peak_df['Sector'].value_counts().to_csv("Sector_Counts_Enhanced.csv", header=["Count"])
peak_df['Industry'].value_counts().to_csv("Industry_Counts_Enhanced.csv", header=["Count"])

# Category-wise sector analysis
category_sector_analysis = peak_df.groupby(['Category', 'Sector']).size().unstack(fill_value=0)
category_sector_analysis.to_csv("Category_Sector_Analysis.csv")

pd.DataFrame(skipped, columns=["Skipped Ticker"]).to_csv("Skipped_Tickers.csv", index=False)

print(f"\n📊 Enhanced Summary:")
print(f"New ATH companies: {len(ath_companies)}")
print(f"Within 5% of ATH: {len(within_5_percent)}")
print(f"Within 10% of ATH: {len(within_10_percent)}")
print(f"Total qualifying companies: {len(peak_df)}")
print(f"Skipped due to no data: {len(skipped)}")

# Print category breakdown by sector
print(f"\n📈 Category Breakdown:")
category_counts = peak_df['Category'].value_counts().sort_index()
for category, count in category_counts.items():
    if category == 0:
        print(f"New ATH (0): {count} companies")
    elif category == 5:
        print(f"Within 5% of ATH (5): {count} companies")
    elif category == 10:
        print(f"Within 10% of ATH (10): {count} companies")

print(f"\n🚀 Starting market cap analysis...")
print("="*50)

try:
    target_date_str = target_fy_end.strftime('%Y-%m-%d')
    print(f"📅 Passing date to scraper: {target_date_str}")

    if not os.path.exists("scraper.py"):
        print("❌ scraper.py not found!")
        print("📂 Available Python files:")
        py_files = [f for f in os.listdir('.') if f.endswith('.py')]
        for f in py_files:
            print(f"   📄 {f}")
        sys.exit(1)  # Exit if scraper.py not found

    print("🔍 Found scraper.py, attempting to run...")

    result = subprocess.run([sys.executable, "scrapers.py", target_date_str], 
                            text=True, 
                            check=True)

    print("✅ Market cap analysis completed successfully!")
    print(result.stdout)

except subprocess.CalledProcessError as e:
    print(f"❌ Error running scraper.py: {e}")
    print(f"Error output: {e.stderr}")
except FileNotFoundError:
    print("❌ scraper.py not found in the current directory!")
except Exception as e:
    print(f"❌ Unexpected error: {e}")

print(f"\n🎉 Complete pipeline finished!")
print(f"📁 Generated files for date: {target_fy_end.strftime('%d_%m_%Y')}")