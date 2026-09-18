from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field
from app.models.recurring_transaction import RecurringFrequency, RecurringStatus, RecurringTransactionType
from app.schemas.category import CategoryResponse


class RecurringBase(BaseModel):
    category_id: int
    type: RecurringTransactionType
    amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=255)
    payment_method: str = Field(default="Other", max_length=50)
    frequency: RecurringFrequency = RecurringFrequency.MONTHLY
    start_date: date


class RecurringCreate(RecurringBase):
    pass


class RecurringUpdate(BaseModel):
    category_id: Optional[int] = None
    type: Optional[RecurringTransactionType] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    payment_method: Optional[str] = Field(None, max_length=50)
    frequency: Optional[RecurringFrequency] = None
    next_occurrence_date: Optional[date] = None
    status: Optional[RecurringStatus] = None


class RecurringResponse(RecurringBase):
    id: int
    user_id: int
    next_occurrence_date: date
    status: RecurringStatus
    last_generated_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True
