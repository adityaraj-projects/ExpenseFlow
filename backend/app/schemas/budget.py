from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.category import CategoryResponse


class BudgetBase(BaseModel):
    category_id: int
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2)


class BudgetResponse(BudgetBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)


class BudgetProgressResponse(BaseModel):
    id: int
    user_id: int
    category_id: int
    category_name: str
    category_icon: str
    category_color: str
    budget_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    percentage_used: float
    month: int
    year: int
    status: str  # "safe", "warning", "exceeded"


class BudgetMonthlySummary(BaseModel):
    month: int
    year: int
    total_budget: Decimal
    total_spent: Decimal
    remaining: Decimal
    percentage_used: float
    items: List[BudgetProgressResponse]
