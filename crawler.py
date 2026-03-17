import re
import urllib.parse
from urllib.parse import urljoin
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Page, TimeoutError # type: ignore

from models import CompanyRequest, Report # type: ignore

class ReportCrawler:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def _filter_reports(self, title: str, expected_types: List[str]) -> str | None:
        """
        Check if the title matches desired report types and does not contain ignored keywords.
        Returns the matched report type or None.
        """
        title_lower = title.lower()
        
        # Ignored keywords - expanded to filter quarterly, interim, and other non-relevant reports
        ignored = [
            # English
            "board resolution", "meeting notice", "earnings forecast", "correction",
            "summary", "semi-annual", "semiannual", "quarterly", "q1", "q2", "q3", "q4",
            "announcement", "notice", "notice of", "supplementary", "amendment",
            "interim", "half year", "half-year", "1st quarter", "2nd quarter",
            "3rd quarter", "4th quarter", "third quarter", "fourth quarter", "supplement",
            # Chinese
            "董事会", "决议", "会议", "预告", "修正", "摘要", "半年度", "季度",
            "一季度", "二季度", "三季度", "四季度", "公告", "通知", "补充", "更正"
        ]
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

    def _load_page_with_retry(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Load page with retry logic for timeout handling"""
        for attempt in range(max_retries):
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                return True
            except TimeoutError:
                if attempt < max_retries - 1:
                    print(f"Timeout, retrying... ({attempt+1}/{max_retries})")
                    page.wait_for_timeout(2000)
                else:
                    print(f"Failed to load {url} after {max_retries} attempts")
                    return False
            except Exception as e:
                print(f"Error loading page: {e}")
                return False
        return False

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
                    
                # 3. Set Date Range
                # Click the date picker
                try:
                    date_picker = page.locator(".el-date-editor .el-range-input").first
                    if date_picker.count() > 0:
                        # Click to open dropdown
                        date_picker.click()
                        page.wait_for_timeout(1000)
                        
                        # Fill in start date and end date
                        inputs = page.locator(".el-date-range-picker__time-header input.el-input__inner").all()
                        if len(inputs) >= 2:
                            inputs[0].fill(f"{req.start_year}-01-01")
                            page.keyboard.press("Enter")
                            inputs[1].fill(f"{req.end_year}-12-31")
                            page.keyboard.press("Enter")
                            
                        # Click the "OK" / Apply button
                        ok_btn = page.locator(".el-picker-panel__footer .el-button--default.el-picker-panel__link-btn").last
                        if ok_btn.is_visible():
                            ok_btn.click()
                except Exception as e:
                    print(f"Warning: Failed to set date range explicitly: {e}")
                    
                # Wait for the results table to load
                page.wait_for_timeout(2000)
                
                # Pagination loop
                for page_num in range(req.max_pages):  # configurable page limit
                    rows = page.locator(".el-table__row, .table-body tr").all()

                    # Detect empty results on first page
                    if not rows and page_num == 0:
                        no_results = page.locator(".no-data, text=暂无数据").count() > 0
                        if no_results:
                            print(f"No results found for {req.ticker}")
                            break
                    for row in rows:
                        try:
                            title_el = row.locator(".ahover, a").first
                            title = title_el.inner_text().strip()
                            
                            date_str = row.locator("td.time, td.date, .time").first.inner_text().strip() if row.locator("td.time, td.date, .time").count() > 0 else f"{req.year}-01-01"
                            
                            href = title_el.get_attribute("href")
                            if not href:
                                continue

                            # Improved URL construction
                            if href.startswith("http"):
                                full_url = href
                            elif "adjunctUrl" in href:
                                full_url = urljoin("https://static.cninfo.com.cn/", href.split("adjunctUrl=")[-1])
                            elif href.startswith("//"):
                                full_url = "https:" + href
                            elif href.startswith("/"):
                                full_url = "http://static.cninfo.com.cn" + href
                            else:
                                full_url = urljoin(page.url, href)

                            # Enhanced year filtering using date_range_mode
                            valid_years = range(req.start_year, req.end_year + 1)
                            year_found = any(str(y) in title or str(y) in date_str for y in valid_years)
                            if not year_found:
                                continue
                                
                            dt_type = self._filter_reports(title, req.document_types)
                            if dt_type:
                                reports.append(Report(
                                    title=title.replace("\\n", "").strip(),
                                    date=date_str,
                                    url=full_url,
                                    type=dt_type,
                                    source="CNINFO"
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

    def _extract_pdf_url(self, url: str, page: Page) -> tuple[str, bool]:
        """Extract underlying PDF from preview wrappers. Returns (pdf_url, is_preview)"""
        preview_patterns = ["/listedco/listconews/", "/disclosure/detail", "view=", "preview="]
        is_preview = any(p in url for p in preview_patterns)

        if not is_preview or url.lower().endswith('.pdf'):
            return url, False

        try:
            preview_page = page.context.new_page()
            preview_page.goto(url, timeout=30000, wait_until="domcontentloaded")
            preview_page.wait_for_timeout(2000)

            pdf_link = preview_page.locator("a[href$='.pdf'], iframe[src$='.pdf']").first
            if pdf_link.count() > 0:
                pdf_href = pdf_link.get_attribute("href") or pdf_link.get_attribute("src")
                if pdf_href:
                    if pdf_href.startswith("http"):
                        preview_page.close()
                        return pdf_href, True
                    elif pdf_href.startswith("//"):
                        preview_page.close()
                        return "https:" + pdf_href, True
                    else:
                        preview_page.close()
                        return urljoin(url, pdf_href), True

            preview_page.close()
            return url, True
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return url, True

    def scrape_hkexnews(self, req: CompanyRequest) -> List[Report]:
        reports = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                # 1. Open Website
                page.goto("https://www.hkexnews.hk/index.htmsearch/titlesearch.xhtml", timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)  # Give page time to fully initialize

                # 2. Search for Company
                search_input = page.locator("#searchStockCode").first
                search_input.wait_for(state="visible", timeout=15000)

                search_input.click()
                page.wait_for_timeout(500)
                search_input.fill("")  # Clear input
                search_input.fill(req.ticker)  # Use fill instead of press_sequentially for reliability
                page.wait_for_timeout(3000)  # Wait longer for autocomplete

                # Wait for dropdown and select the first suggestion
                autocomplete_worked = False
                try:
                    # Try multiple selectors for autocomplete
                    autocomplete_selectors = [
                        ".autocomplete-suggestion-list li",
                        ".ui-autocomplete li",
                        "[role='listbox'] li",
                        ".suggestions li"
                    ]

                    for selector in autocomplete_selectors:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click()
                            autocomplete_worked = True
                            page.wait_for_timeout(1000)
                            break

                    if not autocomplete_worked:
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)
                except Exception as e:
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)

                # 3. Fill date range
                start_date = f"{req.start_year}/01/01"
                end_date = f"{req.end_year}/12/31"

                try:
                    date_from = page.locator("#searchDate-From, input[name='dateFrom']").first
                    date_to = page.locator("#searchDate-To, input[name='dateTo']").first

                    if date_from.count() > 0:
                        # Input is often readonly, so we use JS evaluation
                        date_from.evaluate(f"el => el.value = '{start_date}'")
                    if date_to.count() > 0:
                        date_to.evaluate(f"el => el.value = '{end_date}'")
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"Warning: could not fill dates: {e}")

                # 4. Click Search button
                search_button_clicked = False
                search_button_selectors = [
                    "button:has-text('Search')",
                    "input[type='submit'][value*='Search']",
                    ".filter__btn-applyFilters-js",
                    "#btnSearch",
                    ".btn-search",
                    "button.search-btn"
                ]

                for selector in search_button_selectors:
                    try:
                        btn = page.locator(selector).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click()
                            search_button_clicked = True
                            break
                    except:
                        continue

                if not search_button_clicked:
                    pass

                page.wait_for_timeout(3000)  # Wait for results to load

                # 5. Wait for results table with multiple selector attempts
                results_found = False
                result_selectors = [
                    ".table-scroll table tbody tr",
                    ".search-result-table tbody tr",
                    "table tbody tr",
                    ".doc-link",
                    "[role='row']"
                ]

                for selector in result_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=10000)
                        if page.locator(selector).count() > 0:
                            results_found = True
                            break
                    except:
                        continue

                if not results_found:
                    return []

                page.wait_for_timeout(2000)  # Give time to render

                # Pagination loop for HKEX
                for page_num in range(req.max_pages):
                    # Try multiple selectors for rows
                    row_selectors = [
                        ".table-scroll table tbody tr",
                        ".search-result-table tbody tr",
                        "table tbody tr",
                        ".result-row"
                    ]

                    rows = []
                    for selector in row_selectors:
                        rows = page.locator(selector).all()
                        if rows:
                            break

                    if not rows:
                        break

                    for row in rows:
                        try:
                            # Try multiple selectors for title/link
                            title = ""
                            title_el = None
                            title_selectors = [".title a", "td a", ".doc-link", "a[href*='listconews']", "a"]
                            for sel in title_selectors:
                                try:
                                    if row.locator(sel).count() > 0:  # type: ignore
                                        title_el = row.locator(sel).first  # type: ignore
                                        title = str(title_el.inner_text().strip())
                                        if title:
                                            break
                                except:
                                    continue

                            if not title or not title_el:
                                continue

                            # Try multiple selectors for date
                            date_str = ""
                            date_selectors = [".datetime", "td.date", ".date", "td:nth-child(1)", "td:first-child"]
                            for sel in date_selectors:
                                if row.locator(sel).count() > 0:  # type: ignore
                                    date_str = str(row.locator(sel).first.inner_text().strip())  # type: ignore
                                    if date_str:
                                        break

                            if not date_str:
                                date_str = f"{req.year}-01-01"  # Fallback date

                            href = title_el.get_attribute("href")  # type: ignore
                            if not href:
                                continue

                            # Improved URL handling
                            if str(href).startswith("http"):
                                full_url = href
                            elif str(href).startswith("//"):
                                full_url = "https:" + href
                            else:
                                full_url = urljoin(page.url, href)

                            # Enhanced year filtering using date_range_mode
                            valid_years = range(req.start_year, req.end_year + 1)
                            year_found = any(str(y) in str(title) or str(y) in str(date_str) for y in valid_years)
                            if not year_found:
                                continue

                            dt_type = self._filter_reports(title, req.document_types)
                            if dt_type:
                                # Extract PDF URL if it's a preview wrapper
                                pdf_url, is_preview = self._extract_pdf_url(full_url, page)
                                final_url = pdf_url if is_preview and pdf_url else full_url

                                reports.append(Report(
                                    title=title.replace("\\n", "").strip(),
                                    date=date_str,
                                    url=final_url,
                                    type=dt_type,
                                    source="HKEX"
                                ))
                        except Exception as e:
                            print(f"Error parsing row on hkex: {e}")

                    # Check for next page
                    try:
                        next_btn = page.locator(".pagination .next, button:has-text('Next'), .pager .next-page").first
                        if next_btn.count() > 0 and next_btn.is_visible() and not next_btn.is_disabled():
                            next_btn.click()
                            page.wait_for_timeout(2000)
                        else:
                            break
                    except Exception:
                        break
            except Exception as e:
                print(f"Error scraping hkexnews for {req.ticker}: {e}")
            finally:
                browser.close()
                
        return self._deduplicate(reports)

    def _deduplicate(self, reports: List[Report]) -> List[Report]:
        """Enhanced deduplication by URL and normalized title"""
        import re

        def normalize_title(title: str) -> str:
            """Normalize title for fuzzy matching"""
            return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', title.lower())

        seen_urls = set()
        seen_titles = set()
        unique_reports = []

        # Sort so we deterministically prefer the first seen
        sorted_reports = sorted(reports, key=lambda r: r.url)

        for r in sorted_reports:
            # Check URL duplication
            if r.url in seen_urls:
                continue

            # Check title similarity
            norm_title = normalize_title(r.title)
            if norm_title in seen_titles:
                continue

            # Add to unique set
            seen_urls.add(r.url)
            seen_titles.add(norm_title)
            unique_reports.append(r)

        return unique_reports

    def _execute_with_retry(self, scraper_func, req: CompanyRequest, max_retries: int = 3) -> List[Report]:
        """Execute scraper with retry logic"""
        import time
        for attempt in range(max_retries):
            try:
                return scraper_func(req)
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Error: {e}, retrying ({attempt+1}/{max_retries})")
                    time.sleep(5)
                else:
                    print(f"Failed after {max_retries} attempts: {e}")
                    return []
        return []

    def run(self, req: CompanyRequest) -> List[Report]:
        # Simple routing based on ticker or website
        t_upper = req.ticker.upper()
        if "HK" in t_upper or (t_upper.isdigit() and len(req.ticker) <= 5):
            return self._execute_with_retry(self.scrape_hkexnews, req)
        else:
            return self._execute_with_retry(self.scrape_cninfo, req)
