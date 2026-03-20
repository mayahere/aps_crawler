import re
import urllib.parse
from urllib.parse import urljoin
from datetime import datetime, timedelta
from typing import List
from playwright.sync_api import sync_playwright, Page, TimeoutError # type: ignore

from models import CompanyRequest, Report # type: ignore
from crawler import filter_reports, execute_with_retry # type: ignore

class CNInfoCrawler:
    def __init__(self, headless: bool = True):
        self.headless = headless

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

    def scrape(self, req: CompanyRequest) -> List[Report]:
        return execute_with_retry(self._scrape_cninfo_internal, req)

    def _scrape_cninfo_internal(self, req: CompanyRequest) -> List[Report]:
        reports = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                # 1. Open Website
                page.goto("https://www.cninfo.com.cn/new/index", timeout=60000, wait_until="domcontentloaded")
                
                # Detect the search input field
                search_input = page.locator("input[placeholder*='代码/简称/拼音'], input[placeholder*='代码'], .search-input input").first
                search_input.wait_for(state="visible", timeout=10000)
                
                # 2. Search for Company
                search_input.click()
                search_input.fill(req.ticker)
                
                # Wait for dropdown
                page.wait_for_timeout(3000)
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
                try:
                    date_picker = page.locator(".el-date-editor .el-range-input").first
                    if date_picker.count() > 0:
                        date_picker.click()
                        page.wait_for_timeout(1000)
                        
                        inputs = page.locator(".el-date-range-picker__time-header input.el-input__inner").all()
                        if len(inputs) >= 2:
                            inputs[0].fill(f"{req.start_year}-01-01")
                            page.keyboard.press("Enter")
                            inputs[1].fill(f"{req.end_year + 2}-12-31")
                            page.keyboard.press("Enter")
                            
                        ok_btn = page.locator(".el-picker-panel__footer .el-button--default.el-picker-panel__link-btn").last
                        if ok_btn.is_visible():
                            ok_btn.click()
                except Exception:
                    pass
                    
                page.wait_for_timeout(2000)
                
                # Pagination loop
                for page_num in range(req.max_pages):
                    rows = page.locator(".no-data").count() > 0 or page.locator("text=暂无数据").count() > 0

                    if not rows and page_num == 0:
                        no_results = page.locator(".no-data, text=暂无数据").count() > 0
                        if no_results:
                            break
                    for row in rows:
                        try:
                            title_el = row.locator(".ahover, a").first
                            title = title_el.inner_text().strip()
                            
                            date_str = row.locator("td.time, td.date, .time").first.inner_text().strip() if row.locator("td.time, td.date, .time").count() > 0 else f"{req.year}-01-01"
                            
                            href = title_el.get_attribute("href")
                            if not href:
                                continue

                            if "/disclosure/detail" in href and "announcementId=" in href:
                                import urllib.parse as urlpa
                                parsed = urlpa.urlparse(href)
                                qs = urlpa.parse_qs(parsed.query)
                                ann_id = qs.get("announcementId", [None])[0]
                                if ann_id:
                                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', str(date_str))
                                    if date_match:
                                        parsed_date = datetime.strptime(date_match.group(0), '%Y-%m-%d')
                                        parsed_date += timedelta(days=1)
                                        clean_date = parsed_date.strftime('%Y-%m-%d')
                                        full_url = f"http://static.cninfo.com.cn/finalpage/{clean_date}/{ann_id}.PDF"
                                    else:
                                        full_url = href
                                else:
                                    full_url = href
                            elif href.startswith("http"):
                                full_url = href
                            elif "adjunctUrl" in href:
                                full_url = urljoin("https://static.cninfo.com.cn/", href.split("adjunctUrl=")[-1])
                            elif href.startswith("//"):
                                full_url = "https:" + href
                            elif href.startswith("/"):
                                full_url = "http://static.cninfo.com.cn" + href
                            else:
                                full_url = urljoin(page.url, href)

                            valid_years = range(req.start_year, req.end_year + 2)
                            year_found = any(str(y) in title for y in valid_years)
                            if not year_found:
                                continue
                                
                            dt_type = filter_reports(title, req.document_types)
                            if dt_type:
                                reports.append(Report(
                                    title=title.replace("\\n", "").strip(),
                                    date=date_str,
                                    url=full_url,
                                    type=dt_type,
                                    source="CNINFO"
                                ))
                        except Exception:
                            pass
                            
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
                
        return reports
