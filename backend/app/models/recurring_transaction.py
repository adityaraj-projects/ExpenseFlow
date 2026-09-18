from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Date, Numeric, ForeignKey, Index, Enum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base
import enum


class RecurringFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class RecurringStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class RecurringTransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    type: Mapped[RecurringTransactionType] = mapped_column(
        Enum(RecurringTransactionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="Other", nullable=False)
    frequency: Mapped[RecurringFrequency] = mapped_column(
        Enum(RecurringFrequency, values_callable=lambda x: [e.value for e in x]),
        default=RecurringFrequency.MONTHLY,
        nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_occurrence_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[RecurringStatus] = mapped_column(
        Enum(RecurringStatus, values_callable=lambda x: [e.value for e in x]),
        default=RecurringStatus.ACTIVE,
        nullable=False,
        index=True
    )
    last_generated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
    category: Mapped["Category"] = relationship("Category")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_recurring_amount"),
        Index("idx_recurring_user_status_next", "user_id", "status", "next_occurrence_date"),
    )

    def __repr__(self) -> str:
        return f"<RecurringTransaction id={self.id} desc='{self.description}' next={self.next_occurrence_date} status='{self.status}'>"
