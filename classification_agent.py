import os
import requests
from typing import Literal

ReportType = Literal["annual_report", "financial_statements", "sustainability_report", "esg_report", "unknown"]

class ClassificationAgent:
    """
    ClassificationAgent is responsible for categorizing discovered reports into predefined
    types based on their title and URL. Uses OpenAI API (gpt-4o) with a keyword-based fallback.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def classify_report(self, title: str, url: str) -> ReportType:
        if not self.api_key:
            print("Warning: OPENAI_API_KEY not set. Falling back to keyword classification.")
            return self._fallback_classification(title, url)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are an expert financial document classifier. Your task is to classify the given corporate report "
            "into exactly one of the following categories based on its title and URL context:\n"
            "- 'annual_report': Annual report or annual report & accounts\n"
            "- 'financial_statements': Consolidated financial statements\n"
            "- 'sustainability_report': Sustainability / ESG report\n"
            "- 'esg_report': ESG data report or ESG data pack\n"
            "- 'unknown': If it does not belong to any of the above.\n\n"
            "Respond ONLY with the exact category name (e.g., 'annual_report'). Do not include any other text, quotes, or formatting."
        )

        user_content = f"Title: {title}\nURL: {url}"

        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": 10,
            "temperature": 0.0
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip().lower()
            
            valid_categories = ["annual_report", "financial_statements", "sustainability_report", "esg_report"]
            for category in valid_categories:
                if category in content:
                    return category
            
            return "unknown"
            
        except Exception as e:
            print(f"Error classifying with OpenAI: {e}. Falling back to keywords.")
            return self._fallback_classification(title, url)

    def _fallback_classification(self, title: str, url: str) -> ReportType:
        text = f"{title} {url}".lower()
        if "sustainability" in text or "可持续发展" in text:
            return "sustainability_report"
        elif "esg" in text or "corporate responsibility" in text or "社会责任" in text or "环境、社会及管治" in text:
            return "esg_report"
        elif "annual report" in text or "integrated" in text or "年度报告" in text or "年报" in text:
            return "annual_report"
        elif "financial statement" in text or "财务报表" in text:
            return "financial_statements"
        return "unknown"
