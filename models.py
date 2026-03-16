from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class CompanyRequest(BaseModel):
    company_name: str = Field(description="Official company name")
    ticker: str = Field(description="Stock exchange ticker symbol")
    year: int = Field(description="Requested reporting year")

class Report(BaseModel):
    title: str
    report_type: Literal["annual_report", "financial_statements", "sustainability_report", "esg_report", "unknown"]
    url: str
    source: str
    source_page: str
    file_type: str = "pdf"

class CompanyResult(BaseModel):
    company_name: str
    ticker: str
    year: int
    reports: List[Report] = []
    status: Literal["success", "partial", "not_found", "pending", "error"] = "pending"

class OutputResult(BaseModel):
    results: List[CompanyResult]
