import json
import argparse
from typing import List
from models import CompanyRequest, CompanyResult, OutputResult
from crawler import ReportCrawler

def process_companies(requests: List[CompanyRequest]) -> OutputResult:
    """
    Main orchestrator function. Takes a list of company requests,
    runs them through the Playwright crawler,
    and returns the structured OutputResult.
    """
    crawler = ReportCrawler(headless=True)
    results = []
    
    for req in requests:
        print(f"\n--- Processing {req.company_name} ({req.ticker}) for year {req.year} ---")
        
        try:
            reports = crawler.run(req)
        except Exception as e:
            print(f"Crawler failed for {req.ticker}: {e}")
            reports = []
            
        company_result = CompanyResult(
            company_name=req.company_name,
            ticker=req.ticker,
            year=req.year,
            reports=reports
        )
        
        results.append(company_result)
        
    return OutputResult(results=results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corporate Report Discovery AI Agent")
    parser.add_argument("--input", type=str, help="JSON file containing list of CompanyRequest objects")
    parser.add_argument("--output", type=str, default="results.json", help="Output JSON file for results")
    parser.add_argument("--demo", action="store_true", help="Run a demo with provided Cninfo and Hkexnews examples")
    parser.add_argument("--headless-off", action="store_true", help="Run browser in headful mode (for debugging)")
    args = parser.parse_args()
    
    requests_list = []
    
    if args.demo:
        requests_list = [
            CompanyRequest(
                website="https://www.cninfo.com.cn/new/index",
                company_name="Shanghai United Imaging Healthcare Co Ltd.", 
                ticker="688271", 
                year=2023,
                document_types=["Annual Report", "ESG Report", "Sustainability Report", "Corporate Social Responsibility Report"]
            ),
            CompanyRequest(
                website="https://www.hkexnews.hk/index.htm",
                company_name="Pacific Basin Shipping Limited", 
                ticker="2343", 
                year=2023,
                document_types=["Annual Report", "ESG Report", "Sustainability Report", "Corporate Social Responsibility Report"]
            )
        ]
    elif args.input:
        import csv
        try:
            with open(args.input, "r") as f:
                if args.input.endswith(".csv"):
                    reader = csv.DictReader(f)
                    for row in reader:
                        requests_list.append(CompanyRequest(
                            company_name=row["company"],
                            year=int(row["year"]),
                            ticker=row["ticker"]
                        ))
                else:
                    data = json.load(f)
                    requests_list = [CompanyRequest(**d) for d in data]
        except Exception as e:
            print(f"Error loading input file: {e}")
            exit(1)
    else:
        print("Please provide --input file or use --demo flag.")
        exit(1)
        
    # Optional override for headless
    if args.headless_off:
        # We need to hack it in this simple script
        # In a real app we'd pass this to process_companies
        global_headless = False
        def process_with_override(reqs):
            crawler = ReportCrawler(headless=global_headless)
            results = []
            for r in reqs:
                print(f"Crawling {r.ticker}")
                results.append(CompanyResult(
                    company_name=r.company_name, ticker=r.ticker, year=r.year, reports=crawler.run(r)
                ))
            return OutputResult(results=results)
        final_output = process_with_override(requests_list)
    else:
        final_output = process_companies(requests_list)
    
    # Save to output
    with open(args.output, "w") as f:
        f.write(final_output.model_dump_json(indent=2))
        
    print(f"\nProcessing complete. Results saved to {args.output}")
