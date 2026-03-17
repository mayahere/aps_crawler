from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class CompanyRequest(BaseModel):
    website: str = Field(default="", description="Target website URL")
    company_name: str = Field(description="Official company name")
    ticker: str = Field(description="Stock exchange ticker symbol")
    year: int = Field(description="Requested reporting year")
    document_types: List[str] = Field(default_factory=list, description="List of target report types")

class Report(BaseModel):
    title: str
    date: str
    url: str
    type: str

class CompanyResult(BaseModel):
    company_name: str
    ticker: str
    year: int
    reports: List[Report] = []

class OutputResult(BaseModel):
    results: List[CompanyResult]
