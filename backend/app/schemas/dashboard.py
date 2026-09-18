from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.transaction import TransactionResponse
from app.schemas.budget import BudgetProgressResponse
from app.schemas.savings_goal import GoalResponse
from app.schemas.reminder import ReminderResponse
from app.schemas.recurring_transaction import RecurringResponse


class DashboardSummary(BaseModel):
    total_balance: Decimal
    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    month_income: Decimal
    month_expense: Decimal
    month_budget: Decimal
    month_budget_spent: Decimal
    month_budget_remaining: Decimal
    budget_percentage_used: float
    active_goals_count: int
    total_saved_in_goals: Decimal


class MonthlyTrendItem(BaseModel):
    period: str  # e.g. "Apr 2026"
    year: int
    month: int
    income: Decimal
    expense: Decimal
    net: Decimal


class CategoryBreakdownItem(BaseModel):
    category_id: int
    category_name: str
    category_icon: str
    category_color: str
    amount: Decimal
    percentage: float


class DashboardData(BaseModel):
    summary: DashboardSummary
    monthly_trend: List[MonthlyTrendItem]
    category_breakdown: List[CategoryBreakdownItem]
    recent_transactions: List[TransactionResponse]
    budget_progress: List[BudgetProgressResponse]
    savings_goals: List[GoalResponse]
    upcoming_reminders: List[ReminderResponse] = []
    upcoming_recurring: List[RecurringResponse] = []
    unread_notifications_count: int = 0

