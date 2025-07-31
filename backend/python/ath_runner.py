import subprocess
import datetime
import os

def run_ath_analysis(target_date=None):
    """
    Runs ATH + market cap pipeline for a given date (default: today)
    Returns the formatted output filename (or None on failure)
    """
    try:
        if not target_date:
            target_date = datetime.date.today().strftime('%Y-%m-%d')

        # Step 1: Run ATH detection
        subprocess.run(['python', 'thread_athh.py', target_date], cwd=os.path.dirname(__file__), check=True)

        # Step 2: Run market cap scraper
        subprocess.run(['python', 'scrapers.py', target_date], cwd=os.path.dirname(__file__), check=True)

        # Return output CSV path
        date_obj = datetime.datetime.strptime(target_date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d_%m_%Y')
        output_filename = f"ATH_companies_with_market_cap_{formatted_date}.csv"

        return output_filename

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        return None
