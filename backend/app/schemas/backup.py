from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BackupUser(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    currency: Optional[str] = "INR"


class BackupCategory(BaseModel):
    name: str
    type: str  # "expense" or "income"
    color: Optional[str] = None
    icon: Optional[str] = None


class BackupTransaction(BaseModel):
    amount: Decimal
    type: str  # "expense" or "income"
    transaction_date: str  # YYYY-MM-DD
    transaction_time: Optional[str] = None
    description: str
    category_name: Optional[str] = None
    source: Optional[str] = "manual"
    source_reference: Optional[str] = None
    external_transaction_id: Optional[str] = None
    external_utr: Optional[str] = None
    notes: Optional[str] = None


class BackupBudget(BaseModel):
    category_name: str
    amount: Decimal
    month: int
    year: int


class BackupSavingsGoal(BaseModel):
    name: str
    target_amount: Decimal
    current_amount: Optional[Decimal] = Decimal("0.00")
    target_date: Optional[str] = None
    status: Optional[str] = "in_progress"


class BackupReminder(BaseModel):
    title: str
    amount: Optional[Decimal] = None
    reminder_date: str  # YYYY-MM-DD
    category_name: Optional[str] = None
    status: Optional[str] = "pending"
    notes: Optional[str] = None


class BackupRecurring(BaseModel):
    description: str
    amount: Decimal
    type: str
    frequency: str
    category_name: Optional[str] = None
    start_date: Optional[str] = None
    next_occurrence_date: Optional[str] = None
    status: Optional[str] = "active"


class BackupPayload(BaseModel):
    application: str = "ExpenseFlow"
    backup_version: str = "1.0"
    created_at: str
    user: Optional[BackupUser] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    categories: List[BackupCategory] = Field(default_factory=list)
    transactions: List[BackupTransaction] = Field(default_factory=list)
    budgets: List[BackupBudget] = Field(default_factory=list)
    savings_goals: List[BackupSavingsGoal] = Field(default_factory=list)
    reminders: List[BackupReminder] = Field(default_factory=list)
    recurring_transactions: List[BackupRecurring] = Field(default_factory=list)


class BackupValidateResponse(BaseModel):
    valid: bool
    application: str
    backup_version: str
    created_at: Optional[str] = None
    user_name: Optional[str] = None
    counts: Dict[str, int]
    message: str


class RestoreItemSummary(BaseModel):
    imported: int
    skipped: int
    failed: int


class BackupRestoreResponse(BaseModel):
    status: str
    summary: Dict[str, RestoreItemSummary]
    total_imported: int
    total_skipped: int
    total_failed: int
    message: str
