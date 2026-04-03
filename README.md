# APS Crawler: Automated Corporate Report Discovery

## 1. Objective
A Python-based tool built with **Playwright** that automatically discovers and retrieves public URLs of corporate reports for a given list of companies and a specified reporting year. 

It currently supports crawling two specific stock exchange disclosure platforms:
* **HKEX News** (Hong Kong Exchange)
* **CNINFO** (China Exchange)

This tool returns structured JSON results containing direct links to the relevant PDF reports, which can also be converted into a flattened CSV format.

## 2. Input Specification
The tool expects a structured CSV or JSON file containing companies to search for. When using a CSV, include headers representing the fields below.

| Field | Type | Required | Description |
| ---- | ---- | ---- | ---- |
| `company` | string | Yes | Official company name |
| `ticker` | string | Yes | Stock exchange ticker symbol |
| `year` | integer | Yes | Requested reporting year |
| `stockex` | string | No | Target exchange (`HKEX` or `CNINFO`). Will be inferred if omitted based on ticker format. |

## 3. Features
* **Automated Web Scraping:** Uses Playwright to interactively navigate, search, set date ranges, and extract documents from official stock exchange sites. Includes smart preview extraction to pull the final PDF URLs directly.
* **Auto-Classification:** Automatically filters and classifies PDFs using a keyword-based matching system against report titles (e.g., matching "Annual Report", "ESG Report", "可持续发展").
* **Smart Filtering:** Ignores announcements, notices, interim reports, and other irrelevant documents using predefined negative keyword lists to minimize noise.


## 4. Expected Output Format
The agent returns **all discovered report URLs corresponding to the requested reporting year**, deduplicated and formatted in a structured JSON.

```json
{
  "results": [
    {
      "company_name": "Pacific Basin Shipping Limited",
      "ticker": "2343",
      "exchange": "HKEX",
      "year": 2023,
      "reports": [
        {
          "title": "Annual Report 2023",
          "date": "2024/03/12",
          "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0312/90299_39434.pdf",
          "type": "Annual Report",
          "source": "HKEX"
        }
      ]
    }
  ]
}
```

## 5. System Requirements and Installation
1. Install Python 3.9+
2. Clone this repository to your local machine.
3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install Playwright browser binaries (this allows the crawler to spin up a headless Chromium browser):
   ```bash
   playwright install chromium
   ```

## 6. API Key Configuration (Optional)

The crawler supports two modes of operation regarding API usage:
* **Without API Key:** The system will rely completely on standard Playwright web scraping and keyword-based filtering rules to perform discovery and classification. This offers full basic functionality without incurring API costs.
* **With API Key (Perplexity and OpenAI):** By supplying API keys, the scraper can leverage AI models for advanced semantic search, improved classification, and more robust querying (e.g., dynamically handling complex ticker symbols or ambiguous company names).

To enable these enhanced features, create a `.env` file in the project's root directory containing your keys:
```env
PERPLEXITY_API_KEY=your_perplexity_api_key
OPENAI_API_KEY=your_openai_api_key
```

## 7. How to Use

### Run the Built-in Demo
Test the crawler using predefined demo companies (e.g., Shanghai United Imaging on CNINFO and Pacific Basin on HKEXNews):
```bash
python main.py --demo
```
*(Optionally include the `--headless-off` flag if you want to visibly watch the web crawler operate for debugging purposes)*

### Run with Custom Input File
You can create an input CSV file (e.g., `data/input/mini.csv`) with your list of companies:
```csv
company,ticker,year,stockex
YIXIN GROUP LIMITED,2858,2024,HKEX
AVIC JONHON OPTRONIC TECHNOLOGY LTD,002179,2024,CNINFO
```

Then run the agent, providing the input and desired output file path. Optional arguments can also be passed at the command line that act as fallbacks:
```bash
python main.py --input data/input/mini.csv --output data/output/results_mini.json
```

### Convert JSON Output to CSV
To convert the resulting nested JSON into a flattened, spreadsheet-ready CSV format:
```bash
python json_to_csv_converter.py data/output/results_mini.json data/output/results_mini.csv
```
The converter will automatically strip internal commas from strings and map all fields into a flat structure.