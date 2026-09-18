from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.savings_goal import GoalStatus


class GoalBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: Decimal = Field(..., gt=0, decimal_places=2)
    target_date: Optional[date] = None
    description: Optional[str] = None


class GoalCreate(GoalBase):
    initial_amount: Optional[Decimal] = Field(Decimal("0.00"), ge=0, decimal_places=2)


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    target_date: Optional[date] = None
    description: Optional[str] = None
    status: Optional[GoalStatus] = None


class GoalDepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    action: str = Field("deposit", pattern="^(deposit|withdraw)$")


class GoalResponse(GoalBase):
    id: int
    user_id: int
    current_amount: Decimal
    remaining_amount: Decimal
    progress_percentage: float
    status: GoalStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
