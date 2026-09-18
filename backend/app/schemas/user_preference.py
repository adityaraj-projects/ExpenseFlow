from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserPreferenceBase(BaseModel):
    notifications_enabled: bool = True
    budget_alerts: bool = True
    reminder_alerts: bool = True
    goal_alerts: bool = True
    recurring_alerts: bool = True
    push_enabled: bool = True


class UserPreferenceUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    budget_alerts: Optional[bool] = None
    reminder_alerts: Optional[bool] = None
    goal_alerts: Optional[bool] = None
    recurring_alerts: Optional[bool] = None
    push_enabled: Optional[bool] = None


class UserPreferenceResponse(UserPreferenceBase):
    user_id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
