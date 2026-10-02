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
    phonepe_income: Optional[Decimal] = Decimal("0.00")
    phonepe_expense: Optional[Decimal] = Decimal("0.00")
    cash_income: Optional[Decimal] = Decimal("0.00")
    cash_expense: Optional[Decimal] = Decimal("0.00")


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


class MonthlySourceBreakdownItem(BaseModel):
    source: str
    label: str
    income: Decimal
    expense: Decimal
    net: Decimal
    income_count: int
    expense_count: int
    total_count: int


class MonthOverMonthComparison(BaseModel):
    prev_month: int
    prev_year: int
    prev_month_name: str
    prev_income: Decimal
    prev_expense: Decimal
    prev_net_savings: Decimal
    prev_savings_rate: float
    income_change_pct: Optional[float] = None
    expense_change_pct: Optional[float] = None
    savings_change_pct: Optional[float] = None
    expense_change_direction: str  # "decreased", "increased", "unchanged", "no_baseline"
    income_change_direction: str   # "increased", "decreased", "unchanged", "no_baseline"
    savings_change_direction: str  # "improved", "decreased", "unchanged", "no_baseline"
    summary_message: str


class MonthlyTopCategoryItem(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    category_icon: str
    category_color: str
    amount: Decimal
    percentage: float
    transaction_count: int


class MonthlyFinancialSummary(BaseModel):
    month: int
    year: int
    month_name: str
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    savings_rate: float
    income_count: int
    expense_count: int
    total_transactions: int
    source_breakdown: List[MonthlySourceBreakdownItem]
    top_categories: List[MonthlyTopCategoryItem]
    comparison: MonthOverMonthComparison
    insights: List[str]
