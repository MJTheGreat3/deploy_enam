import csv
import os
from dateutil import parser
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "frontend", "static", "assets", "csv", "news_repository.csv"))

ALLOWED_CATEGORIES_PRIORITY = [
    'Stock',
    'IPOs',
    'Companies',
    'Markets',
    'Economy',
    'Finance',
    'Business',
    'Industry',
    'Technology',
    'Research',
    'Other'
]

SPECIAL_WORD_MAPPING = {
    'money': 'Finance',
    'banking': 'Finance',
    'economic': 'Economy',
    'equity': 'Markets',
    'commodities': 'Industry',
    'commodity': 'Industry',
    'asset': 'Business'
}

def clean_time_string(time_str):
    """
    Convert '14:57 | Jun 30, 2025' or other mixed formats to 'YYYY-MM-DD HH:MM:SS'
    """
    time_str = time_str.strip()
    if "|" in time_str:
        try:
            time_part, date_part = [s.strip() for s in time_str.split("|", 1)]
            combined = f"{date_part} {time_part}"
            dt = parser.parse(combined)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"[Warning] Could not parse split time '{time_str}': {e}")
            return time_str
    else:
        try:
            dt = parser.parse(time_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"[Warning] Could not parse time '{time_str}': {e}")
            return time_str

def normalize_category_word(word):
    """
    Normalize plural to singular basic forms for matching.
    E.g. 'stocks' -> 'stock'
    """
    word = word.lower().strip()
    if word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word

def map_single_category(raw_cat):
    """
    Maps a single category string to one of the allowed categories using the specified rules.
    """
    raw_cat_clean = raw_cat.strip()
    if not raw_cat_clean:
        return "Other"

    cat_lower = raw_cat_clean.lower()

    # 1. Check special words mapping
    for special_word, mapped in SPECIAL_WORD_MAPPING.items():
        if special_word in cat_lower:
            return mapped

    # 2. Exact match (singular/plural) against allowed categories
    normalized_input = normalize_category_word(cat_lower)
    for allowed in ALLOWED_CATEGORIES_PRIORITY:
        if normalize_category_word(allowed.lower()) == normalized_input:
            return allowed

    # 3. Substring / partial match in priority order
    for allowed in ALLOWED_CATEGORIES_PRIORITY:
        allowed_lower = allowed.lower()
        if allowed_lower in cat_lower:
            return allowed

    # 4. If no match at all
    return "Other"

def clean_category_string(category_str):
    """
    Splits multiple categories, normalizes each according to mapping and rules,
    rejoins them in a comma-separated string.
    """
    if not category_str:
        return "Other"

    categories = [c.strip() for c in category_str.split(',') if c.strip()]
    cleaned = [map_single_category(cat) for cat in categories]

    # Deduplicate while preserving order
    seen = set()
    result = []
    for cat in cleaned:
        if cat not in seen:
            seen.add(cat)
            result.append(cat)

    return ', '.join(result)

def is_recent_enough(time_str, days=14):
    """
    Returns True if the parsed datetime is within the last 'days' days.
    """
    try:
        dt = parser.parse(time_str)
        cutoff = datetime.now() - timedelta(days=days)
        return dt >= cutoff
    except Exception as e:
        print(f"[Warning] Could not parse time for filtering '{time_str}': {e}")
        return False  # If can't parse, exclude it

def clean_csv_in_place(csv_file):
    cleaned_rows = []

    # Try utf-8-sig first
    try:
        with open(csv_file, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if 'Time' in row:
                    row['Time'] = clean_time_string(row['Time'])
                if 'Category' in row:
                    row['Category'] = clean_category_string(row['Category'])

                if 'Time' in row and is_recent_enough(row['Time']):
                    cleaned_rows.append(row)
                else:
                    if 'Time' in row:
                        print(f"[INFO] Removing old article dated {row['Time']}")
    except UnicodeDecodeError:
        print("[Warning] utf-8-sig failed, retrying with latin1 encoding...")
        with open(csv_file, newline='', encoding='latin1') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if 'Time' in row:
                    row['Time'] = clean_time_string(row['Time'])
                if 'Category' in row:
                    row['Category'] = clean_category_string(row['Category'])

                if 'Time' in row and is_recent_enough(row['Time']):
                    cleaned_rows.append(row)
                else:
                    if 'Time' in row:
                        print(f"[INFO] Removing old article dated {row['Time']}")

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"Cleaning complete. File '{csv_file}' updated in place.")


if __name__ == "__main__":
    clean_csv_in_place(CSV_FILE)
