import os
import requests
import json
from typing import List, Dict, Any
from models import CompanyRequest

class SearchAgent:
    """
    SearchAgent is responsible for discovering candidate URLs for corporate reports.
    It uses the Perplexity API to query stock exchange disclosure platforms, 
    official company websites, and external search engines.
    """
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.api_url = "https://api.perplexity.ai/chat/completions"

    def get_candidate_reports(self, request: CompanyRequest) -> tuple[List[Dict[str, Any]], str]:
        """
        Executes search queries and returns a list of candidate report dictionaries and the official company name if found.
        """
        if not self.api_key:
            print("Warning: PERPLEXITY_API_KEY not set. Cannot perform external search.")
            # Still proceed with CNINFO if possible
            
        queries = self._generate_search_queries(request)
        all_reports = []
        seen_urls = set()
        official_name = ""

        # Handle direct API query for CNINFO
        clean_ticker = ''.join(filter(str.isdigit, request.ticker))
        if len(clean_ticker) == 6 or ".SZ" in request.ticker.upper() or ".SS" in request.ticker.upper():
            cninfo_reports, found_name = self._search_cninfo_api(request.ticker, request.year)
            official_name = found_name
            for r in cninfo_reports:
                url = r.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_reports.append(r)

        # Handle Perplexity fallback queries
        for q, source_type in queries:
            if not self.api_key: break
            print(f"Executing search: {q}")
            reports = self._execute_search_query(q, source_type)
            for r in reports:
                url = r.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_reports.append(r)

        return all_reports, official_name

    def _generate_search_queries(self, request: CompanyRequest) -> List[tuple[str, str]]:
        """
        Generates a list of search queries and their corresponding source types.
        Returns: [(query, source_type), ...]
        """
        queries = []
        year = request.year
        company = request.company_name
        ticker = request.ticker.strip().upper()
        clean_ticker = ''.join(filter(str.isdigit, ticker))

        # 1. Stock Exchange Disclosure Platforms
        if len(clean_ticker) == 4 or ".HK" in ticker:
            # HKEX News
            hkex_base_query = f'site:www1.hkexnews.hk "{company}" {year}'
            queries.append((f'{hkex_base_query} "Annual Report" filetype:pdf', "hkex"))
            queries.append((f'{hkex_base_query} "Sustainability Report" OR "ESG Report" filetype:pdf', "hkex"))
            
        elif len(clean_ticker) == 6 or ".SZ" in ticker or ".SS" in ticker:
            # CNINFO is now handled directly via API in get_candidate_reports
            pass

        # 2. Official Website / External Search (Fallback)
        queries.append((f'"{company}" official website {year} "Annual Report" filetype:pdf', "external"))
        queries.append((f'"{company}" official website {year} "Sustainability Report" OR "ESG Report" filetype:pdf', "external"))

        return queries
        
    def _get_cninfo_org_id(self, ticker: str) -> str:
        """
        Look up the CNINFO orgId for a given ticker.
        """
        url = "http://www.cninfo.com.cn/new/information/topSearch/query"
        params = {"keyWord": ticker, "maxNum": 10}
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        try:
            response = requests.post(url, data=params, headers=headers, timeout=10)
            res = response.json()
            for item in res:
                if item.get("code") == ticker:
                    return item.get("orgId")
        except Exception as e:
            print(f"Error getting orgId for {ticker}: {e}")
        return ""

    def _search_cninfo_api(self, ticker: str, year: int) -> tuple[List[Dict[str, Any]], str]:
        """
        Directly queries the CNINFO API to fetch PDF announcements for the given ticker and year.
        Uses orgId for precise filtering and returns the official company name.
        """
        clean_ticker = ''.join(filter(str.isdigit, ticker))
        if not clean_ticker:
            return [], ""
            
        org_id = self._get_cninfo_org_id(clean_ticker)
        if not org_id:
            print(f"Warning: Could not find orgId for {clean_ticker}. Search might be less accurate.")
            stock_param = f"{clean_ticker},"
        else:
            stock_param = f"{clean_ticker},{org_id}"
            
        url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        
        # Determine exchange column: szse or sse
        column = "szse"
        if clean_ticker.startswith(("60", "68")):
            column = "sse"
            
        categories = ["category_ndbg_szsh", "category_shzr_szsh"]
        
        all_found = []
        official_name = ""
        for cat in categories:
            data = {
                "pageNum": 1,
                "pageSize": 30,
                "tabName": "fulltext",
                "column": column,
                "stock": stock_param,
                "category": cat,
                "seDate": f"{year}-01-01~{year+1}-12-31",
                "isHLtitle": "true"
            }
            
            try:
                print(f"Executing CNINFO API search for ticker: {clean_ticker}, category: {cat}")
                response = requests.post(url, headers=headers, data=data, timeout=15)
                response.raise_for_status()
                res_json = response.json()
                announcements = res_json.get("announcements", [])
                
                if not announcements:
                    continue
                    
                for ann in announcements:
                    # Strict Ticker Filter
                    sec_code = ann.get("secCode")
                    if sec_code and sec_code != clean_ticker:
                        continue

                    # Extract official name if not set
                    if not official_name:
                        official_name = ann.get("secName", "")

                    title = ann.get("announcementTitle", "")
                    adj_url = ann.get("adjunctUrl", "")
                    if adj_url and title:
                        clean_title = title.replace("<em>", "").replace("</em>", "")
                        if str(year) in clean_title or str(year+1) in clean_title:
                            full_url = f"https://static.cninfo.com.cn/{adj_url}"
                            all_found.append({
                                "title": clean_title,
                                "url": full_url,
                                "source": "cninfo",
                                "source_page": ""
                            })
            except Exception as e:
                print(f"Error executing CNINFO API search for {cat}: {e}")
            
        return all_found, official_name

    def _execute_search_query(self, query: str, source_type: str) -> List[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = (
            "You are an expert financial data researcher. Your task is to return a strict JSON array of objects, "
            "where each object represents a discovered PDF report matching the user's query. "
            "Each object MUST have the following keys:\n"
            "- 'title': The full title of the report\n"
            "- 'url': The direct PDF URL\n"
            f"- 'source': Always set this to '{source_type}'\n"
            "- 'source_page': The URL of the webpage where this PDF was found (or empty string if unknown).\n"
            "Do not include any other text, markdown formatting outside the JSON, or explanations. "
            "If no valid reports are found, return []."
        )

        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "max_tokens": 1000,
            "temperature": 0.1
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            
            # Clean up markdown if model incorrectly outputs it
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()

            reports = json.loads(content)
            if isinstance(reports, list):
                # Ensure all are dicts with url
                return [r for r in reports if isinstance(r, dict) and r.get("url", "").startswith("http")]
        except Exception as e:
            print(f"Error querying Perplexity or parsing response: {e}")
            
        return []

