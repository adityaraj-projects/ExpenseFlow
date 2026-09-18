from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category, CategoryType
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetResponse,
    BudgetProgressResponse,
    BudgetMonthlySummary
)

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("", response_model=BudgetMonthlySummary)
def get_budgets(
    month: Optional[int] = Query(None, ge=1, le=12, description="Target month (1-12)"),
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Target year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all category budgets for the specified month and year,
    including real-time spent amount, remaining balance, and usage percentage.
    """
    today = date.today()
    target_month = month if month is not None else today.month
    target_year = year if year is not None else today.year

    # 1. Fetch budgets for user in this month/year
    budgets = (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(
            Budget.user_id == current_user.id,
            Budget.month == target_month,
            Budget.year == target_year
        )
        .all()
    )

    # 2. Fetch actual expenses grouped by category for this month/year
    expenses = (
        db.query(
            Transaction.category_id,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("spent")
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == TransactionType.EXPENSE,
            extract("year", Transaction.transaction_date) == target_year,
            extract("month", Transaction.transaction_date) == target_month
        )
        .group_by(Transaction.category_id)
        .all()
    )

    spent_map = {row.category_id: Decimal(str(row.spent)) for row in expenses}

    items: List[BudgetProgressResponse] = []
    total_budget = Decimal("0.00")
    total_spent = Decimal("0.00")

    for b in budgets:
        b_amount = Decimal(str(b.amount))
        spent = spent_map.get(b.category_id, Decimal("0.00"))
        remaining = b_amount - spent
        pct = float(round((spent / b_amount) * 100, 1)) if b_amount > 0 else 0.0

        if pct > 100.0:
            status_str = "exceeded"
        elif pct >= 80.0:
            status_str = "warning"
        else:
            status_str = "safe"

        total_budget += b_amount
        total_spent += spent

        items.append(
            BudgetProgressResponse(
                id=b.id,
                user_id=b.user_id,
                category_id=b.category_id,
                category_name=b.category.name if b.category else "Unknown",
                category_icon=b.category.icon if b.category else "tag",
                category_color=b.category.color if b.category else "#6366F1",
                budget_amount=b_amount,
                spent_amount=spent,
                remaining_amount=remaining,
                percentage_used=pct,
                month=b.month,
                year=b.year,
                status=status_str
            )
        )

    overall_remaining = total_budget - total_spent
    overall_pct = float(round((total_spent / total_budget) * 100, 1)) if total_budget > 0 else 0.0

    return BudgetMonthlySummary(
        month=target_month,
        year=target_year,
        total_budget=total_budget,
        total_spent=total_spent,
        remaining=overall_remaining,
        percentage_used=overall_pct,
        items=items
    )


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    budget_in: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a monthly budget for an expense category."""
    # Check category ownership and type
    category = db.query(Category).filter(
        Category.id == budget_in.category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found."
        )

    if category.type == CategoryType.INCOME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budgets can only be set for Expense or Both type categories."
        )

    # Check duplicate budget entry
    existing = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category_id == budget_in.category_id,
        Budget.month == budget_in.month,
        Budget.year == budget_in.year
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A budget for '{category.name}' in {budget_in.month}/{budget_in.year} already exists."
        )

    new_budget = Budget(
        user_id=current_user.id,
        category_id=budget_in.category_id,
        amount=budget_in.amount,
        month=budget_in.month,
        year=budget_in.year
    )
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    new_budget.category = category
    return new_budget


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int,
    budget_in: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the budget amount for an existing monthly budget."""
    budget = (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found."
        )

    budget.amount = budget_in.amount
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a monthly budget."""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found."
        )

    db.delete(budget)
    db.commit()
    return {"message": "Budget deleted successfully."}
