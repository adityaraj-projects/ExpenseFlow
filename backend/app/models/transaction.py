from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Date, Numeric, ForeignKey, CheckConstraint, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base
import enum


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    recurring_transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("recurring_transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")
    recurring_transaction: Mapped[Optional["RecurringTransaction"]] = relationship("RecurringTransaction")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_trans_amount"),
        Index("idx_trans_user_date", "user_id", "transaction_date"),
        Index("idx_trans_recurring_date", "recurring_transaction_id", "transaction_date"),
    )

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} type='{self.type}' amount={self.amount} date={self.transaction_date}>"
