#!/usr/bin/env python3
"""
UK Sponsor CSV Update Script
Downloads the latest UK sponsor list from GOV.UK

Usage:
    python update_sponsors.py
"""

import csv
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from io import StringIO

# Configuration
CSV_URL = "https://assets.publishing.service.gov.uk/media/69aab491d620c14fa183ede3/2026-03-06_-_Worker_and_Temporary_Worker.csv"
CSV_OUTPUT = "uk_sponsors.csv"
BACKUP_DIR = "backups"


def download_csv(url: str) -> bool:
    """Download the latest CSV from GOV.UK"""
    print(f"Downloading from: {url}")
    
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read().decode('utf-8', errors='ignore')
            
        # Parse and validate CSV
        reader = csv.DictReader(StringIO(content))
        rows = list(reader)
        
        if len(rows) < 1000:
            print(f"Error: Downloaded file only has {len(rows)} rows - too few")
            return False
        
        print(f"Downloaded {len(rows)} sponsor records")
        
        # Create backup if current file exists
        if os.path.exists(CSV_OUTPUT):
            os.makedirs(BACKUP_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"uk_sponsors_{timestamp}.csv")
            os.replace(CSV_OUTPUT, backup_path)
            print(f"Backed up old file to: {backup_path}")
        
        # Write new file
        with open(CSV_OUTPUT, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        
        print(f"Updated {CSV_OUTPUT} successfully!")
        return True
        
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def count_records(csv_file: str) -> int:
    """Count records in CSV"""
    try:
        with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f) - 1  # Minus header
    except:
        return 0


def main():
    print("=" * 50)
    print("UK Sponsor CSV Updater")
    print("=" * 50)
    print(f"Target: {CSV_URL}")
    print()
    
    # Check current records
    if os.path.exists(CSV_OUTPUT):
        current_count = count_records(CSV_OUTPUT)
        print(f"Current records: {current_count}")
    else:
        print("No existing CSV found")
        current_count = 0
    
    print()
    
    # Download new data
    success = download_csv(CSV_URL)
    
    if success:
        new_count = count_records(CSV_OUTPUT)
        print(f"\nNew records: {new_count}")
        print(f"Change: {new_count - current_count:+d}")
        return 0
    else:
        print("\nUpdate failed")
        return 1


if __name__ == '__main__':
    exit(main())
