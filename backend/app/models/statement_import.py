from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base


class StatementImport(Base):
    __tablename__ = "statement_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), default="phonepe", nullable=False, index=True)
    statement_period: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="statement_imports")

    __table_args__ = (
        Index("idx_stmt_user_period", "user_id", "statement_period"),
        Index("idx_stmt_user_date", "user_id", "imported_at"),
    )

    def __repr__(self) -> str:
        return f"<StatementImport id={self.id} user_id={self.user_id} period='{self.statement_period}' status='{self.status}'>"
