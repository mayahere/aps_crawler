import re
import time
from typing import List, Optional
from models import CompanyRequest, Report # type: ignore

def filter_reports(title: str, expected_types: List[str]) -> Optional[str]:
    """
    Check if the title matches desired report types and does not contain ignored keywords.
    Returns the matched report type or None.
    """
    title_lower = title.lower()
    
    ignored = [
        "board resolution", "meeting notice", "earnings forecast", "correction",
        "summary", "semi-annual", "semiannual", "quarterly", "q1", "q2", "q3", "q4",
        "announcement", "notice", "notice of", "supplementary", "amendment",
        "interim", "half year", "half-year", "1st quarter", "2nd quarter",
        "3rd quarter", "4th quarter", "third quarter", "fourth quarter", "supplement", "letter", 
        "notification", "procedures", "terms", "committee", "reference", "letter of", "general meeting",
        "董事会", "决议", "会议", "预告", "修正", "摘要", "半年度", "季度",
        "一季度", "二季度", "三季度", "四季度", "公告", "通知", "补充", "更正",
        "form", "proxy", "circular", "annual general meeting", "重大差错", "责任追究","制度","审计委员会","规程"
    ]
    for ig in ignored:
        if ig in title_lower:
            return None
            
    type_mapping = {
        "Annual Report": ["annual report", "年度报告", "年报"],
        "ESG Report": ["esg", "environmental, social and governance"],
        "Sustainability Report": ["sustainability", "可持续发展"],
        "Corporate Social Responsibility Report": ["csr", "social responsibility", "社会责任报告"]
    }
    
    found_type = None
    for r_type, keywords in type_mapping.items():
        if any(kw in title_lower for kw in keywords):
            found_type = r_type
            break
            
    if found_type and expected_types:
        if found_type in expected_types:
            return found_type
        else:
            return None
    
    return found_type

def deduplicate_reports(reports: List[Report]) -> List[Report]:
    """Enhanced deduplication by URL and normalized title"""
    def normalize_title(title: str) -> str:
        return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', title.lower())

    seen_urls = set()
    seen_titles = set()
    unique_reports = []

    sorted_reports = sorted(reports, key=lambda r: r.url)

    for r in sorted_reports:
        if r.url in seen_urls:
            continue
        norm_title = normalize_title(r.title)
        if norm_title in seen_titles:
            continue

        seen_urls.add(r.url)
        seen_titles.add(norm_title)
        unique_reports.append(r)

    return unique_reports

def execute_with_retry(scraper_func, req: CompanyRequest, max_retries: int = 3) -> List[Report]:
    """Execute scraper with retry logic"""
    for attempt in range(max_retries):
        try:
            return scraper_func(req)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return []
    return []

# Avoid circular imports by loading the crawlers AFTER the utility functions are mounted
from cninfo_crawler import CNInfoCrawler # type: ignore
from hkexnews_crawler import HKEXNewsCrawler # type: ignore

class ReportCrawler:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.cninfo = CNInfoCrawler(headless=headless)
        self.hkex = HKEXNewsCrawler(headless=headless)

    def filter_consolidated_reports(self, reports: List[Report], targeted_year: int) -> List[Report]:
        unique_reports = deduplicate_reports(reports)
        final_reports = []
        ignored = [
            "board resolution", "meeting notice", "earnings forecast", "correction",
            "summary", "semi-annual", "semiannual", "quarterly", "q1", "q2", "q3", "q4",
            "announcement", "notice", "notice of", "supplementary", "amendment",
            "interim", "half year", "half-year", "1st quarter", "2nd quarter",
            "3rd quarter", "4th quarter", "third quarter", "fourth quarter", "supplement", "letter", 
            "notification", "procedures", "terms", "committee", "reference", "letter of", "general meeting",
            "董事会", "决议", "会议", "预告", "修正", "摘要", "半年度", "季度",
            "一季度", "二季度", "三季度", "四季度", "公告", "通知", "补充", "更正",
            "form", "proxy", "circular", "annual general meeting"
        ]
        
        for r in unique_reports:
            t_lower = r.title.lower()
            if not any(ig in t_lower for ig in ignored):
                # Extra explicit check for strict year mismatching
                years_in_title = re.findall(r'\b(20\d{2})\b', r.title)
                if years_in_title and str(targeted_year) not in years_in_title:
                    continue
                final_reports.append(r)
        
        print(f"Result: found {len(final_reports)} reports.")
        return final_reports

    def run(self, req: CompanyRequest) -> List[Report]:
        t_upper = req.ticker.upper()
        if req.stockex and req.stockex.upper() == "HKEX":
            reports = self.hkex.scrape(req)
        elif req.stockex and req.stockex.upper() == "CNINFO":
            reports = self.cninfo.scrape(req)
        elif "HK" in t_upper or (t_upper.isdigit() and len(req.ticker) <= 5):
            reports = self.hkex.scrape(req)
        else:
            reports = self.cninfo.scrape(req)
            
        return self.filter_consolidated_reports(reports, req.year)
