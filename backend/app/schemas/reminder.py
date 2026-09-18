from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field
from app.models.reminder import ReminderRecurrence, ReminderStatus
from app.schemas.category import CategoryResponse


class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, ge=0)
    category_id: Optional[int] = None
    reminder_date: date
    reminder_time: Optional[str] = Field(None, max_length=8)  # e.g. "09:30"
    recurrence: ReminderRecurrence = ReminderRecurrence.ONCE
    notification_enabled: bool = True


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, ge=0)
    category_id: Optional[int] = None
    reminder_date: Optional[date] = None
    reminder_time: Optional[str] = Field(None, max_length=8)
    recurrence: Optional[ReminderRecurrence] = None
    status: Optional[ReminderStatus] = None
    notification_enabled: Optional[bool] = None


class ReminderSnooze(BaseModel):
    days: int = Field(default=1, ge=1, le=365)


class ReminderResponse(ReminderBase):
    id: int
    user_id: int
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True
