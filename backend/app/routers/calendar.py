import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, case, func

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category


router = APIRouter(prefix="/calendar", tags=["Calendar & Daily Finance"])


def _apply_filters(
    query,
    source: Optional[str] = None,
    tx_type: Optional[str] = None,
    category_id: Optional[int] = None
):
    if tx_type and tx_type.lower() in ["income", "expense"]:
        query = query.filter(Transaction.type == tx_type.lower())

    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    if source and source.strip() and source.lower() != "all":
        s_lower = source.strip().lower()
        if s_lower in ["cash", "manual"]:
            query = query.filter(
                or_(
                    Transaction.source == "cash",
                    Transaction.source == "manual",
                    Transaction.source.is_(None)
                )
            )
        elif s_lower == "phonepe":
            query = query.filter(Transaction.source == "phonepe")
        else:
            query = query.filter(Transaction.source == source.strip())

    return query


@router.get("/month")
def get_calendar_month(
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    source: Optional[str] = Query(None, description="Source filter ('all', 'phonepe', 'cash')"),
    type: Optional[str] = Query(None, description="Type filter ('income', 'expense')"),
    category_id: Optional[int] = Query(None, description="Category filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Fetch comprehensive calendar month data:
    - Month-level totals (income, expense, net savings)
    - Day-by-day indicator map (income, expense, both, none)
    - Full transaction list for the month with exact time, source badge, category info
    """
    _, last_day = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    base_query = db.query(Transaction).join(Category).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    )

    filtered_query = _apply_filters(base_query, source=source, tx_type=type, category_id=category_id)
    txs = filtered_query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).all()

    # Pre-populate all days in the month
    days_data: Dict[str, Dict[str, Any]] = {}
    for d in range(1, last_day + 1):
        dt_str = f"{year:04d}-{month:02d}-{d:02d}"
        days_data[dt_str] = {
            "date": dt_str,
            "day": d,
            "income": 0.0,
            "expense": 0.0,
            "net": 0.0,
            "count": 0,
            "has_income": False,
            "has_expense": False,
            "indicator": "none"  # "none", "income", "expense", "both"
        }

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    items_list = []

    for tx in txs:
        amt = tx.amount
        dt_key = tx.transaction_date.strftime("%Y-%m-%d")

        if dt_key in days_data:
            day_entry = days_data[dt_key]
            day_entry["count"] += 1
            if tx.type == TransactionType.INCOME:
                day_entry["income"] += float(amt)
                day_entry["has_income"] = True
                total_income += amt
            else:
                day_entry["expense"] += float(amt)
                day_entry["has_expense"] = True
                total_expense += amt
            day_entry["net"] = round(day_entry["income"] - day_entry["expense"], 2)

        items_list.append({
            "id": tx.id,
            "transaction_date": dt_key,
            "transaction_time": tx.transaction_time,
            "description": tx.description,
            "amount": float(tx.amount),
            "type": tx.type.value,
            "source": tx.source or "manual",
            "category_id": tx.category_id,
            "category_name": tx.category.name if tx.category else "General",
            "category_icon": tx.category.icon if tx.category else "tag",
            "category_color": tx.category.color if tx.category else "#6366F1",
            "external_transaction_id": tx.external_transaction_id,
            "source_reference": tx.source_reference
        })

    # Set indicator colors for each day
    for dt_key, day_entry in days_data.items():
        if day_entry["has_income"] and day_entry["has_expense"]:
            day_entry["indicator"] = "both"
        elif day_entry["has_income"]:
            day_entry["indicator"] = "income"
        elif day_entry["has_expense"]:
            day_entry["indicator"] = "expense"
        else:
            day_entry["indicator"] = "none"

    net_balance = total_income - total_expense

    return {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "days_in_month": last_day,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net_balance": float(net_balance),
        "total_transactions": len(txs),
        "days": days_data,
        "transactions": items_list
    }


@router.get("/day")
def get_calendar_day(
    target_date: date = Query(..., alias="date", description="Target date (YYYY-MM-DD)"),
    source: Optional[str] = Query(None, description="Source filter ('all', 'phonepe', 'cash')"),
    type: Optional[str] = Query(None, description="Type filter ('income', 'expense')"),
    category_id: Optional[int] = Query(None, description="Category filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Fetch exact financial records for a single selected date:
    - Daily Income
    - Daily Expenses
    - Daily Net Balance
    - Full list of transactions sorted newest first with exact time and source badges
    """
    base_query = db.query(Transaction).join(Category).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date == target_date
    )

    filtered_query = _apply_filters(base_query, source=source, tx_type=type, category_id=category_id)
    txs = filtered_query.order_by(Transaction.id.desc()).all()

    income_sum = sum((t.amount for t in txs if t.type == TransactionType.INCOME), Decimal("0.00"))
    expense_sum = sum((t.amount for t in txs if t.type == TransactionType.EXPENSE), Decimal("0.00"))
    net_sum = income_sum - expense_sum

    transactions_list = []
    for tx in txs:
        transactions_list.append({
            "id": tx.id,
            "transaction_date": tx.transaction_date.strftime("%Y-%m-%d"),
            "transaction_time": tx.transaction_time,
            "description": tx.description,
            "amount": float(tx.amount),
            "type": tx.type.value,
            "source": tx.source or "manual",
            "category_id": tx.category_id,
            "category_name": tx.category.name if tx.category else "General",
            "category_icon": tx.category.icon if tx.category else "tag",
            "category_color": tx.category.color if tx.category else "#6366F1",
            "external_transaction_id": tx.external_transaction_id,
            "source_reference": tx.source_reference
        })

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "formatted_date": target_date.strftime("%d %B %Y"),
        "total_income": float(income_sum),
        "total_expense": float(expense_sum),
        "net_balance": float(net_sum),
        "transaction_count": len(txs),
        "transactions": transactions_list
    }
