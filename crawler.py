import re
import urllib.parse
from urllib.parse import urljoin
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Page, TimeoutError

from models import CompanyRequest, Report

class ReportCrawler:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def _filter_reports(self, title: str, expected_types: List[str]) -> str:
        """
        Check if the title matches desired report types and does not contain ignored keywords.
        Returns the matched report type or None.
        """
        title_lower = title.lower()
        
        # Ignored keywords
        ignored = ["board resolution", "meeting notice", "earnings forecast", "correction", "董事会", "决议", "会议", "预告", "修正"]
        for ig in ignored:
            if ig in title_lower:
                return None
                
        # Matching keywords
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
                
        # If expected_types are provided, optionally filter by them. The prompt says "filter by document type"
        # but also "filter relevant documents... extract where title contains keywords". 
        # We just return the found type if it matches any known types, or maybe just return found_type.
        
        # If user explicitly specified document_types, we should ensure it matches one
        if found_type and expected_types:
            # check if found_type in expected_types
            if found_type in expected_types:
                return found_type
            else:
                return None
        
        return found_type

    def scrape_cninfo(self, req: CompanyRequest) -> List[Report]:
        reports = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                # 1. Open Website
                page.goto("https://www.cninfo.com.cn/new/index", timeout=60000, wait_until="domcontentloaded")
                
                # 3. Detect the search input field labeled Code / abbreviation / pinyin
                # Usually it's an input with placeholder "代码/简称/拼音"
                search_input = page.locator("input[placeholder*='代码/简称/拼音'], input[placeholder*='代码'], .search-input input").first
                search_input.wait_for(state="visible", timeout=10000)
                
                # 2. Search for Company
                search_input.click()
                search_input.fill(req.ticker)
                
                # Wait for dropdown
                page.wait_for_timeout(3000)
                # Select the matching suggestion
                suggests = page.locator(".el-autocomplete-suggestion li:visible").all()
                clicked = False
                for sug in suggests:
                    try:
                        if req.ticker in sug.inner_text():
                            sug.click()
                            clicked = True
                            break
                    except:
                        pass
                        
                if not clicked and len(suggests) > 0:
                    suggests[0].click()
                elif not clicked:
                    page.keyboard.press("Enter")
                    
                # Wait for the results table to load
                page.wait_for_timeout(2000)
                
                # Pagination loop
                for page_num in range(10):  # limit to 10 pages for safety
                    rows = page.locator(".el-table__row, .table-body tr").all()
                    for row in rows:
                        try:
                            title_el = row.locator(".ahover, a").first
                            title = title_el.inner_text().strip()
                            
                            date_str = row.locator("td.time, td.date, .time").first.inner_text().strip() if row.locator("td.time, td.date, .time").count() > 0 else f"{req.year}-01-01"
                            
                            href = title_el.get_attribute("href")
                            if not href:
                                continue
                                
                            full_url = urljoin(page.url, href)
                            if "adjunctUrl" in href:
                                full_url = full_url 
                            elif not full_url.startswith("http"):
                                full_url = "http://static.cninfo.com.cn/" + href.lstrip("/")
                                
                            if str(req.year) not in title and str(req.year) not in date_str and str(req.year+1) not in date_str:
                                continue
                                
                            dt_type = self._filter_reports(title, req.document_types)
                            if dt_type:
                                reports.append(Report(
                                    title=title.replace("\\n", "").strip(),
                                    date=date_str,
                                    url=full_url,
                                    type=dt_type
                                ))
                        except Exception as e:
                            pass
                            
                    # Try to go to next page
                    next_btn = page.locator("button.btn-next").first
                    if next_btn.is_visible() and not next_btn.is_disabled():
                        next_btn.click()
                        page.wait_for_timeout(2000)
                    else:
                        break
            except Exception as e:
                print(f"Error scraping cninfo for {req.ticker}: {e}")
            finally:
                browser.close()
                
        return self._deduplicate(reports)

    def scrape_hkexnews(self, req: CompanyRequest) -> List[Report]:
        reports = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                # 1. Open Website
                page.goto("https://www1.hkexnews.hk/search/titlesearch.xhtml", timeout=60000, wait_until="domcontentloaded")
                
                # 3. Detect search input labeled "Stock Code"
                search_input = page.locator("#searchStockCode").first
                search_input.wait_for(state="visible", timeout=10000)
                
                # 2. Search for Company
                search_input.click()
                search_input.fill("")  # Clear input
                search_input.press_sequentially(req.ticker, delay=100)
                page.wait_for_timeout(2000)
                
                # Wait for dropdown and select the first suggestion
                try:
                    page.wait_for_selector(".autocomplete-suggestion-list li", timeout=10000)
                    page.locator(".autocomplete-suggestion-list li").first.click()
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"Warning: could not click HKEX dropdown suggestion. {e}")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(1000)
                
                # Fill dates
                start_date = f"{req.year}/01/01"
                end_date = f"{req.year+1}/12/31"
                try:
                    page.locator("#searchDate-From").first.fill(start_date)
                    page.locator("#searchDate-To").first.fill(end_date)
                except:
                    pass
                
                # Click Query / Search
                search_btn = page.locator(".filter__btn-applyFilters-js, #btnSearch, .btn-search").first
                if search_btn.is_visible():
                    search_btn.click()
                    
                page.wait_for_selector(".table-scroll table tbody tr, .doc-link, .search-result-table tbody tr", timeout=15000)
                page.wait_for_timeout(2000) # give it time to render
                
                rows = page.locator(".table-scroll table tbody tr, .search-result-table tbody tr").all()
                for row in rows:
                    try:
                        title_el = row.locator(".title a, td a, .doc-link").first
                        title = title_el.inner_text().strip()
                        
                        date_str = row.locator(".datetime, td.date, td:nth-child(1)").first.inner_text().strip()
                        print(f"DEBUG Hkex Fetch: '{title}', date: '{date_str}'")
                        
                        href = title_el.get_attribute("href")
                        if not href:
                            continue
                            
                        full_url = urljoin(page.url, href)
                        
                        # Use req.year
                        if str(req.year) not in title and str(req.year) not in date_str and str(req.year+1) not in date_str:
                            continue
                            
                        dt_type = self._filter_reports(title, req.document_types)
                        if dt_type:
                            reports.append(Report(
                                title=title.replace("\\n", "").strip(),
                                date=date_str,
                                url=full_url,
                                type=dt_type
                            ))
                    except Exception as e:
                        print(f"Error parsing row on hkex: {e}")
            except Exception as e:
                print(f"Error scraping hkexnews for {req.ticker}: {e}")
            finally:
                browser.close()
                
        return self._deduplicate(reports)

    def _deduplicate(self, reports: List[Report]) -> List[Report]:
        unique = {}
        for r in reports:
            if r.url not in unique:
                unique[r.url] = r
        return list(unique.values())

    def run(self, req: CompanyRequest) -> List[Report]:
        # Simple routing based on ticker or website
        t_upper = req.ticker.upper()
        if "HK" in t_upper or t_upper.isdigit() and len(req.ticker) <= 5:
            return self.scrape_hkexnews(req)
        else:
            return self.scrape_cninfo(req)
