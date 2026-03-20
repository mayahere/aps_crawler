# Requirement: AI Agent for Automated Corporate Report Discovery

## 1. Objective
Build an **AI-powered agent** that automatically discovers and retrieves **public URLs of corporate reports** for a given list of companies and a specified reporting year.
The agent should prioritize **stock exchange disclosure platforms**, specifically:

* **HKEX News** (Hong Kong Exchange)
* **CNINFO** (China Exchange)

The system should return **structured results containing validated direct report URLs**.

This agent will support downstream workflows such as:

* Financial analysis
* ESG data extraction
* Document ingestion pipelines
* Automated report monitoring

---

# 2. Input Specification
The system will receive a list of companies with the following attributes.
| Field        | Type    | Required | Description                                        |
| ------------ | ------- | -------- | -------------------------------------------------- |
| company_name | string  | Yes      | Official company name                              |
| ticker       | string  | Yes      | Stock exchange ticker symbol                       |
| year         | integer | Yes      | Requested reporting year                           |
| stockex      | string  | No       | Target exchange (`HKEX` or `CNINFO`) explicitly    |

# 3. Expected Output

The agent should return **all discovered report URLs corresponding to the requested reporting year**.

### Output Format

```json
{
  "results": [
    {
      "company_name": "HSBC Holdings",
      "ticker": "0005.HK",
      "year": 2024,
      "reports": [
        {
          "title": "HSBC Annual Report and Accounts 2024",
          "report_type": "annual_report",
          "url": "https://example.com/hsbc_annual_report_2024.pdf",
          "source": "hkex",
          "source_page": "https://www1.hkexnews.hk/",
          "file_type": "pdf"
        },
        {
          "title": "HSBC Sustainability Report 2024",
          "report_type": "sustainability_report",
          "url": "https://example.com/hsbc_sustainability_report_2024.pdf",
          "source": "hkex",
          "source_page": "https://www1.hkexnews.hk/",
          "file_type": "pdf"
        }
      ],
      "status": "success"
    }
  ]
}
```

---

# 4. Report Types to Retrieve

The agent should identify and classify reports into the following categories.

### Core Reports

| Type                 | Description                               |
| -------------------- | ----------------------------------------- |
| annual_report        | Annual report or annual report & accounts |
| financial_statements | Consolidated financial statements           |

### ESG / Sustainability Reports

| Type                  | Description                      |
| --------------------- | -------------------------------- |
| sustainability_report | Sustainability / ESG report      |
| esg_report            | ESG data report or ESG data pack |

### Keyword Mapping (for classification)

Example keywords:

Annual Reports:

* "Annual Report"
* "Annual Report and Accounts"
* "Consolidated Financial Statements"
* "Integrated Annual Report"

ESG / Sustainability:

* "Sustainability Report"
* "ESG Report"
* "Corporate Responsibility Report"

---

# 5. Agent Search Strategy

The agent should follow the search priority below.

### Step 1: Stock Exchange Disclosure Platforms
The agent should first attempt to retrieve reports from official disclosure platforms.

### CNINFO (China A-share)
If ticker matches pattern:
```
XXXXXX
XXXXXX

```

Search:

```
https://www.cninfo.com.cn/new/index
```

Tasks:

1. Query disclosure database using ticker
2. Filter announcements for the requested year
3. Extract PDF links from announcement pages
4. Filter relevant reports using report classification rules

---

### HKEX News (Hong Kong)

If ticker matches pattern:

```
XXXX
```

Search:

```
https://www1.hkexnews.hk/
```

Tasks:

1. Search filings using ticker
2. Filter filings for the requested year
3. Extract PDF report URLs
4. Classify reports using title keywords

---

# Step 2: Official Company Website

If reports are not found in stock exchange sources:

1. Identify the **official company website**.

Example search:

```
"Company Name" official website
```

2. Validate the domain:

Indicators of authenticity:

* investor relations section
* corporate domain
* financial reports pages

3. Crawl typical report locations:

Examples:

```
/investors
/investor-relations
/reports
/financial-reports
/esg
/sustainability
```

4. Extract all PDF links and classify report types.

---

# Step 3: External Search

If reports are still not found, use external search.

The agent should query search engines using structured queries such as:

```
"Company Name" 2024 "Annual Report" filetype:pdf
"Company Name" 2024 "Sustainability Report" filetype:pdf
"Company Name" 2024 ESG report filetype:pdf
site:companydomain.com "2024" report filetype:pdf
```

Use **Perplexity API** to retrieve search results and candidate URLs.

---

# 6. Filtering and Validation Rules
The agent must validate results before returning them.

## Year Validation
Accept reports referencing the requested reporting year.
Valid patterns include:

```
2024
FY2024
2024 Annual Report
Financial Year 2024
```

Note:
Some reports may be **published in the following year**.
Example:
```
2024 Annual Report (published in 2025)
```

---

## File Validation
Each report URL must satisfy:
* HTTP response = **200**
* Content-Type = **application/pdf**
* File size > 0

Accepted file types:
```
PDF
```

---

## Source Priority
When multiple versions exist, prioritize sources as follows:
1. Stock exchange disclosures
2. Official company website
3. External sources

---

## Deduplication
The agent should remove duplicate reports based on:
* identical URLs
* identical file names
* highly similar titles

Example duplicates:

```
HSBC_Annual_Report_2024.pdf
HSBC-Annual-Report-2024.pdf
```

---

# 7. Status Logic

Each company should receive one of the following statuses.

| Status    | Description                                                            |
| --------- | ---------------------------------------------------------------------- |
| success   | At least **2 report categories found** (e.g., annual + sustainability) |
| partial   | Only **one report type** found                                         |
| not_found | No valid reports located                                               |

# 8. Agent Architecture
The system should consist of the following components.

### 1. Search Agent
Responsible for discovering candidate URLs.
Tools:
* Perplexity API
* Exchange site crawler
* Domain discovery

### 2. Extraction Agent
Responsible for extracting:
* report titles
* PDF links
* metadata

### 3. Classification Agent
Using **OpenAI API**, classify report type:
* annual_report
* financial_statements
* sustainability_report
* esg_report

### 4. Validation Module
Handles:
* link validation
* year filtering
* deduplication


# 9. LLM and Tools

| Component      | Tool                  |
| -------------- | --------------------- |
| Search         | Perplexity API        |
| Classification | OpenAI API            |
| Crawling       | Web crawler / scraper |
| Validation     | HTTP + file checks    |

---

# 10. How to Use

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
The agent uses the Perplexity API for searching and the OpenAI API for classification.
You can export them in your terminal or create a `.env` file in the project directory:

```bash
export PERPLEXITY_API_KEY="your-perplexity-key"
export OPENAI_API_KEY="your-openai-key"
```
*(Note: If API keys are not provided, the agent will fall back to basic keyword matching and will not perform external Perplexity searches).*

### 3. Run the Agent

**Run the Built-in Demo:**
To test the agent using the predefined demo companies (HSBC and Ping An):
```bash
python main.py --demo
```

**Run with Custom Input File:**
Create an input CSV file (e.g., `input_data.csv`) with your list of companies. The system expects headers for `company`, `ticker`, `year`, and optionally `stockex`:
```csv
company,ticker,year,stockex
YIXIN GROUP LIMITED,2858,2024,HKEX
AVIC JONHON OPTRONIC TECHNOLOGY LTD,002179,2024,CNINFO
```

Then run the agent:
```bash
python main.py --input input_data.csv --output results.json
```

The results will be saved in the specified output JSON file.

### 4. Convert JSON Output to CSV

To convert the final nested JSON output into a flattened, spreadsheet-ready CSV format:
```bash
python json_to_csv_converter.py results.json results.csv
```
The converter will automatically strip internal commas from strings and map all fields into a flat structure.
```