import requests
import json

def search_cninfo_searchkey(query, column="szse"):
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    
    data = {
        "pageNum": 1,
        "pageSize": 10,
        "tabName": "fulltext",
        "column": column,
        "stock": "", 
        "searchkey": query,
        "category": "",
        "seDate": "2024-01-01~2025-12-31",
        "isHLtitle": "true"
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        res_json = response.json()
        announcements = res_json.get("announcements", [])
        if not announcements:
            print(f"No announcements found for query: {query}")
            return
            
        print(f"--- Results for: {query} ---")
        for ann in announcements:
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            adj_url = ann.get("adjunctUrl", "")
            if adj_url:
                full_url = f"https://static.cninfo.com.cn/{adj_url}"
                print(f"{title}: {full_url}")
                
    except Exception as e:
        print(f"Error querying CNINFO API: {e}")

print("Testing searchkey for Guangdong Provincial Expressway...")
search_cninfo_searchkey("000429 2024 年度报告", "szse")

print("\nTesting searchkey for By-health...")
search_cninfo_searchkey("300146 2024 年度报告", "szse")
search_cninfo_searchkey("300146 2024 可持续发展报告", "szse")
