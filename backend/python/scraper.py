import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers import bulk_block, company_data

def main(scrape_type="all"):
    if scrape_type == "all":
        bulk_block.run_bulk_block_scrapers()
        company_data.run_company_scrapers()
    elif scrape_type == "portfolio":
        company_data.run_company_scrapers()
    elif scrape_type == "new":
        company_data.run_company_scrapers(only_new=True)
    else:
        print(f"Invalid scrape type: {scrape_type}")

if __name__ == "__main__":
    scrape_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    main(scrape_type)
