from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, DateTime, Numeric, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="budgets")
    category: Mapped["Category"] = relationship("Category", back_populates="budgets")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_budget_amount"),
        CheckConstraint("month >= 1 AND month <= 12", name="chk_budget_month"),
        UniqueConstraint("user_id", "category_id", "month", "year", name="uq_user_cat_month_year"),
        Index("idx_budgets_lookup", "user_id", "month", "year"),
    )

    def __repr__(self) -> str:
        return f"<Budget id={self.id} user_id={self.user_id} category_id={self.category_id} amount={self.amount} period={self.month}/{self.year}>"
