#!/usr/bin/env python3
"""
JSON to CSV Converter
Converts crawler output from JSON format to CSV format
"""

import json
import csv
import sys
from pathlib import Path


def convert_json_to_csv(json_file_path, csv_file_path=None):
    """
    Convert JSON crawler output to CSV format

    Args:
        json_file_path: Path to input JSON file
        csv_file_path: Path to output CSV file (optional, defaults to same name with .csv extension)
    """
    # Read JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Determine output file path
    if csv_file_path is None:
        csv_file_path = Path(json_file_path).with_suffix('.csv')

    # Flatten the data structure
    rows = []
    for company_data in data.get('results', []):
        company_name = company_data.get('company_name', '')
        ticker = company_data.get('ticker', '')
        year = company_data.get('year', '')

        for report in company_data.get('reports', []):
            row = {
                'title': report.get('title', ''),
                'date': report.get('date', ''),
                'url': report.get('url', ''),
                'type': report.get('type', ''),
                'company': company_name,
                'ticker': ticker,
                'year': year
            }
            
            # Remove commas from all values (including Chinese commas and enumeration commas)
            for key, value in row.items():
                if isinstance(value, str):
                    row[key] = value.replace(',', '').replace('，', '').replace('、', '')
                elif value is not None:
                    row[key] = str(value).replace(',', '').replace('，', '').replace('、', '')
                    
            rows.append(row)

    # Write to CSV
    if rows:
        fieldnames = ['title', 'date', 'url', 'type', 'company', 'ticker', 'year']
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✓ Converted {len(rows)} reports from {len(data.get('results', []))} companies")
        print(f"✓ Output saved to: {csv_file_path}")
    else:
        print("⚠ No data found to convert")


def main():
    if len(sys.argv) < 2:
        print("Usage: python json_to_csv_converter.py <input_json_file> [output_csv_file]")
        print("\nExample:")
        print("  python json_to_csv_converter.py data/output/test4.json")
        print("  python json_to_csv_converter.py data/output/test4.json data/output/test4.csv")
        sys.exit(1)

    json_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        convert_json_to_csv(json_file, csv_file)
    except FileNotFoundError:
        print(f"✗ Error: File '{json_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON format - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
