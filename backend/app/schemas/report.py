from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel


class ReportSummary(BaseModel):
    start_date: date
    end_date: date
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    savings_rate: float
    transaction_count: int
    daily_average_expense: Decimal


class ReportTimeSeriesItem(BaseModel):
    date_label: str
    income: Decimal
    expense: Decimal
    net: Decimal
    exact_date: Optional[str] = None


class ReportCategoryStatItem(BaseModel):
    category_id: int
    category_name: str
    category_icon: str
    category_color: str
    type: str
    amount: Decimal
    percentage: float
    transaction_count: int


class ComprehensiveReport(BaseModel):
    timeframe: str
    summary: ReportSummary
    time_series: List[ReportTimeSeriesItem]
    expense_categories: List[ReportCategoryStatItem]
    income_categories: List[ReportCategoryStatItem]
