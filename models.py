from pydantic import BaseModel, Field  # type: ignore
from typing import List, Literal, Optional

class CompanyRequest(BaseModel):
    website: str = Field(default="", description="Target website URL")
    company_name: str = Field(description="Official company name")
    ticker: str = Field(description="Stock exchange ticker symbol")
    year: int = Field(description="Requested reporting year")
    document_types: List[str] = Field(
        default_factory=lambda: [
            "Annual Report",
            "ESG Report",
            "Sustainability Report",
            "Corporate Social Responsibility Report"
        ],
        description="List of target report types"
    )
    date_range_mode: Literal["single_year", "year_and_next", "last_3_years"] = Field(
        default="last_3_years",
        description="Date range strategy for report search"
    )
    max_pages: int = Field(default=20, description="Maximum pages to crawl (safety limit)")

    @property
    def start_year(self) -> int:
        """Calculate start year based on date_range_mode"""
        if self.date_range_mode == "last_3_years":
            return self.year - 2
        return self.year

    @property
    def end_year(self) -> int:
        """Calculate end year based on date_range_mode"""
        if self.date_range_mode == "single_year":
            return self.year
        elif self.date_range_mode == "year_and_next":
            return self.year + 1
        else:  # last_3_years
            return self.year

class Report(BaseModel):
    title: str
    date: str
    url: str
    type: str
    source: str

class CompanyResult(BaseModel):
    company_name: str
    ticker: str
    exchange: str
    year: int
    reports: List[Report] = []

class OutputResult(BaseModel):
    results: List[CompanyResult]
