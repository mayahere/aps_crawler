import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
import re
from models import Report
from classification_agent import ClassificationAgent

class ValidationModule:
    """
    Validates discovered reports based on year, HTTP accessibility (PDF), and deduplicate.
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.classification_agent = ClassificationAgent()

    def is_valid_year(self, title: str, expected_year: int) -> bool:
        """
        Validates if the report title references the expected reporting year.
        Reports published in year Y+1 for year Y are valid if they explicitly state 'Y' or 'Y+1'.
        """
        # If title doesn't contain any year-like number, we might conservatively accept it,
        # but the spec says "Accept reports referencing the requested reporting year."
        # We enforce finding the year string.
        year_str = str(expected_year)
        if year_str in title:
            return True
            
        next_year_str = str(expected_year + 1)
        if next_year_str in title:
            return True
            
        # Also check URLs just in case title doesn't have it but URL does
        return False

    def is_valid_pdf_link(self, url: str) -> bool:
        """
        Validates the URL is a reachable PDF.
        """
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            if response.status_code not in (200, 301, 302):
                response = self.session.get(url, timeout=10, stream=True)
                if response.status_code != 200:
                    return False
            
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
                return False
                
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) == 0:
                return False
                
            return True
        except Exception as e:
            print(f"Validation failed for URL {url}: {e}")
            return False

    def deduplicate(self, reports: List[Report]) -> List[Report]:
        """
        Deduplicates reports based on URL, filename, and similar titles.
        Source priority: hkex > cninfo > official website > external.
        """
        priority_map = {"hkex": 1, "cninfo": 1, "company_website": 2, "external": 3}
        reports.sort(key=lambda r: priority_map.get(r.source, 99))
        
        unique_reports = []
        seen_urls = set()
        seen_filenames = set()
        seen_titles = set()
        
        def safe_filename(url: str) -> str:
            path = urlparse(url).path
            return path.split('/')[-1].lower()
            
        def normalized_title(title: str) -> str:
            return re.sub(r'[^a-z0-9]', '', title.lower())

        for r in reports:
            if r.url in seen_urls:
                continue
                
            fname = safe_filename(r.url)
            # Only deduplicate by filename if it looks like a meaningful PDF file name
            if fname and fname.endswith('.pdf') and fname not in ('report.pdf', 'annual_report.pdf'):
                if fname in seen_filenames:
                    continue
                
            ntitle = normalized_title(r.title)
            if ntitle in seen_titles:
                continue
                
            seen_urls.add(r.url)
            if fname:
                seen_filenames.add(fname)
            seen_titles.add(ntitle)
            
            unique_reports.append(r)
            
        return unique_reports
        
    def process_and_validate(self, candidate_dicts: List[Dict[str, Any]], expected_year: int) -> List[Report]:
        valid_reports = []
        
        for cand in candidate_dicts:
            title = cand.get("title", "")
            url = cand.get("url", "")
            
            if not url or not title:
                continue
                
            # If title missing year, we can check URL
            if not self.is_valid_year(title, expected_year) and not self.is_valid_year(url, expected_year):
                print(f"Year {expected_year} validation failed for: {title} / {url}")
                continue
                
            if not self.is_valid_pdf_link(url):
                print(f"PDF validation failed for: {url}")
                continue
                
            report_type = self.classification_agent.classify_report(title, url)
            
            r = Report(
                title=title,
                report_type=report_type,
                url=url,
                source=cand.get("source", "external"),
                source_page=cand.get("source_page", "")
            )
            valid_reports.append(r)
            
        return self.deduplicate(valid_reports)
