import json
import argparse
from typing import List
from models import CompanyRequest, CompanyResult, OutputResult
from search_agent import SearchAgent
from validation import ValidationModule
from dotenv import load_dotenv

load_dotenv()


def process_companies(requests: List[CompanyRequest]) -> OutputResult:
    """
    Main orchestrator function. Takes a list of company requests,
    runs them through Search -> Classification -> Validation,
    and returns the structured OutputResult.
    """
    search_agent = SearchAgent()
    validation_module = ValidationModule()
    
    results = []
    
    for req in requests:
        print(f"\n--- Processing {req.company_name} ({req.ticker}) for year {req.year} ---")
        
        # 1. Search & Extract Candidates
        candidates, official_name = search_agent.get_candidate_reports(req)
        
        # Update name if found
        display_name = official_name if official_name else req.company_name
        
        print(f"Discovered {len(candidates)} candidate URLs from search.")
        
        # 2. Classify, Validate & Deduplicate
        valid_reports = validation_module.process_and_validate(candidates, req.year)
        print(f"Validated and kept {len(valid_reports)} unique reports.")
        
        # 3. Determine Status
        status = "not_found"
        if valid_reports:
            # Check unique report types to determine success or partial
            types_found = {r.report_type for r in valid_reports if r.report_type != "unknown"}
            if len(types_found) >= 2:
                status = "success"
            else:
                status = "partial"
                
        company_result = CompanyResult(
            company_name=display_name,
            ticker=req.ticker,
            year=req.year,
            reports=valid_reports,
            status=status
        )
        
        results.append(company_result)
        
    return OutputResult(results=results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corporate Report Discovery AI Agent")
    parser.add_argument("--input", type=str, help="JSON file containing list of CompanyRequest objects")
    parser.add_argument("--output", type=str, default="results.json", help="Output JSON file for results")
    parser.add_argument("--demo", action="store_true", help="Run a demo with HSBC and Ping An")
    args = parser.parse_args()
    
    requests_list = []
    
    if args.demo:
        requests_list = [
            CompanyRequest(company_name="HSBC Holdings", ticker="0005.HK", year=2024),
            CompanyRequest(company_name="Ping An Insurance", ticker="601318", year=2024)
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
        
    final_output = process_companies(requests_list)
    
    # Save to output
    with open(args.output, "w") as f:
        # Pydantic v2 serialization
        f.write(final_output.model_dump_json(indent=2))
        
    print(f"\nProcessing complete. Results saved to {args.output}")
