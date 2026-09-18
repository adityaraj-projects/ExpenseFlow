from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Date, Numeric, ForeignKey, Index, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base
import enum


class ReminderRecurrence(str, enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SNOOZED = "snoozed"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    reminder_date: Mapped[date] = mapped_column(Date, nullable=False)
    reminder_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # HH:MM
    recurrence: Mapped[ReminderRecurrence] = mapped_column(
        Enum(ReminderRecurrence, values_callable=lambda x: [e.value for e in x]),
        default=ReminderRecurrence.ONCE,
        nullable=False
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, values_callable=lambda x: [e.value for e in x]),
        default=ReminderStatus.PENDING,
        nullable=False,
        index=True
    )
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
    category: Mapped[Optional["Category"]] = relationship("Category")

    __table_args__ = (
        Index("idx_reminders_user_status_date", "user_id", "status", "reminder_date"),
    )

    def __repr__(self) -> str:
        return f"<Reminder id={self.id} title='{self.title}' date={self.reminder_date} status='{self.status}'>"
