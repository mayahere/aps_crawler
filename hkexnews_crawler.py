import urllib.parse
from urllib.parse import urljoin
from typing import List
from playwright.sync_api import sync_playwright, Page, TimeoutError # type: ignore

from models import CompanyRequest, Report # type: ignore
from crawler import filter_reports, execute_with_retry # type: ignore

class HKEXNewsCrawler:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def _extract_pdf_url(self, url: str, page: Page) -> tuple[str, bool]:
        """Extract underlying PDF from preview wrappers."""
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
                    elif pdf_href.startswith("/"):
                        preview_page.close()
                        return "https://www1.hkexnews.hk" + pdf_href, True
                    else:
                        preview_page.close()
                        return urljoin(url, pdf_href), True

            preview_page.close()
            return url, True
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return url, True

    def scrape(self, req: CompanyRequest) -> List[Report]:
        return execute_with_retry(self._scrape_hkexnews_internal, req)

    def _scrape_hkexnews_internal(self, req: CompanyRequest) -> List[Report]:
        reports = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                # Step B1 — Open Website
                page.goto("https://www1.hkexnews.hk/search/titlesearch.xhtml", timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Step B2 — Search Company
                search_input = page.locator("#searchStockCode").first
                search_input.wait_for(state="visible", timeout=15000)

                search_input.click()
                page.wait_for_timeout(500)
                
                def try_search(term: str) -> bool:
                    search_input.fill("") 
                    search_input.fill(term) 
                    page.wait_for_timeout(3000) 

                    autocomplete_selectors = [
                        "tr.autocomplete-suggestion",
                        ".autocomplete-suggestion-list li",
                        ".ui-autocomplete li",
                        "[role='listbox'] li",
                        ".suggestions li"
                    ]

                    for selector in autocomplete_selectors:
                        elements = page.locator(selector).all()
                        if elements:
                            clicked = False
                            for el in elements:
                                try:
                                    text = el.inner_text().lower()
                                    if term.lower() in text or (term.isdigit() and str(int(term)) in text):
                                        el.click()
                                        clicked = True
                                        break
                                except:
                                    continue
                            
                            if not clicked and len(elements) > 0:
                                elements[0].click()
                                clicked = True
                                
                            if clicked:
                                page.wait_for_timeout(1000)
                                return True
                    return False

                # 1) Try Ticker
                autocomplete_worked = try_search(req.ticker)
                
                # 2) Fallback to Name
                if not autocomplete_worked and req.company_name:
                    autocomplete_worked = try_search(req.company_name)
                    
                if not autocomplete_worked:
                    return []

                # Step B3 — Set Date Range
                from datetime import datetime
                current_year = datetime.now().year
                target_end_year = req.end_year + 2
                
                start_date = f"{req.start_year}/01/01"
                end_date = f"{min(target_end_year, current_year)}/12/31"
                
                # If target_end_year >= current_year, just use today's exact date as a safer upper bound
                if target_end_year >= current_year:
                    end_date = datetime.now().strftime("%Y/%m/%d")

                try:
                    date_from = page.locator("#searchDate-From, input[name='dateFrom']").first
                    date_to = page.locator("#searchDate-To, input[name='dateTo']").first

                    if date_from.count() > 0:
                        date_from.evaluate(f"el => el.value = '{start_date}'")
                    if date_to.count() > 0:
                        date_to.evaluate(f"el => el.value = '{end_date}'")
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Step B4 — Execute Search
                search_button_clicked = False
                search_button_selectors = [
                    ".filter__btn-applyFilters-js",
                    "a.filter__btn-applyFilters-js",
                    "button:has-text('Search')",
                    "input[type='submit'][value*='Search']",
                    "#btnSearch",
                    ".btn-search",
                    "button.search-btn",
                    # homepage specific search btn
                    ".search-btn a.search",
                    ".search-btn img[alt='Search']"
                ]

                # We can also just press enter if we are in the input!
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
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000) 

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

                page.wait_for_timeout(2000)

                # Pagination loop
                for page_num in range(req.max_pages):
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
                            # Step B6 — Extract Links
                            title = ""
                            title_el = None
                            title_selectors = [".title a", "td a", ".doc-link", "a[href*='listconews']", "a"]
                            for sel in title_selectors:
                                try:
                                    if row.locator(sel).count() > 0:  # type: ignore
                                        title_el = row.locator(sel).first  # type: ignore
                                        title = str(title_el.inner_text().strip()) # type: ignore
                                        if title:
                                            break
                                except:
                                    continue

                            if not title or not title_el:
                                continue

                            date_str = ""
                            date_selectors = [".datetime", "td.date", ".date", "td:nth-child(1)", "td:first-child"]
                            for sel in date_selectors:
                                if row.locator(sel).count() > 0:  
                                    date_str = str(row.locator(sel).first.inner_text().strip())  
                                    if date_str:
                                        break

                            if not date_str:
                                date_str = f"{req.year}-01-01" 

                            href = title_el.get_attribute("href")  # type: ignore
                            if not href:
                                continue

                            if str(href).startswith("http"):
                                full_url = str(href)
                            elif str(href).startswith("//"):
                                full_url = "https:" + str(href)
                            elif str(href).startswith("/"):
                                full_url = "https://www1.hkexnews.hk" + str(href)
                            else:
                                full_url = urljoin("https://www1.hkexnews.hk", str(href))

                            dt_type = filter_reports(title, req.document_types)
                            
                            if dt_type:
                                negative_filters = ["interim", "quarterly", "circular", "notice", "announcement", "form", "proxy", "summary"]
                                if any(nf in str(title).lower() for nf in negative_filters):  # type: ignore
                                    continue
                                
                                valid_years = range(req.start_year, req.end_year + 3) # Up to +2
                                year_found = any(str(y) in str(title) or str(y) in str(date_str) for y in valid_years)
                                if not year_found:
                                    continue

                                pdf_url, is_preview = self._extract_pdf_url(full_url, page)
                                final_url = pdf_url if is_preview and pdf_url else full_url

                                reports.append(Report(
                                    title=title.replace("\\n", "").strip(),
                                    date=date_str,
                                    url=final_url,
                                    type=dt_type,
                                    source="HKEX"
                                ))
                        except Exception:
                            pass

                    try:
                        next_btn = page.locator(".pagination .next, button:has-text('Next'), .pager .next-page").first
                        if next_btn.count() > 0 and next_btn.is_visible() and not next_btn.is_disabled():
                            next_btn.click()
                            page.wait_for_timeout(2000)
                        else:
                            break
                    except Exception:
                        break
            except Exception:
                pass
            finally:
                browser.close()
                
        return reports
