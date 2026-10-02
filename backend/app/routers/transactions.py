import math
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, or_
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    PaginatedTransactions
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=PaginatedTransactions)
def get_transactions(
    search: Optional[str] = Query(None, description="Search description or category name"),
    type: Optional[TransactionType] = Query(None, description="Filter by income or expense"),
    category_id: Optional[int] = Query(None, description="Filter by specific category"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    min_amount: Optional[Decimal] = Query(None, ge=0, description="Minimum amount filter"),
    max_amount: Optional[Decimal] = Query(None, ge=0, description="Maximum amount filter"),
    source: Optional[str] = Query(None, description="Filter by source: 'phonepe', 'cash', 'manual', 'all'"),
    sort_by: str = Query("date", pattern="^(date|amount)$", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(15, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List transactions with rich filtering, search, sorting, and pagination.
    Includes aggregate totals (total_income, total_expense) matching the filtered scope.
    """
    base_query = db.query(Transaction).join(Category).filter(Transaction.user_id == current_user.id)

    if search:
        search_pattern = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                Transaction.description.ilike(search_pattern),
                Category.name.ilike(search_pattern)
            )
        )

    if type:
        base_query = base_query.filter(Transaction.type == type)

    if category_id:
        base_query = base_query.filter(Transaction.category_id == category_id)

    if start_date:
        base_query = base_query.filter(Transaction.transaction_date >= start_date)

    if end_date:
        base_query = base_query.filter(Transaction.transaction_date <= end_date)

    if min_amount is not None:
        base_query = base_query.filter(Transaction.amount >= min_amount)

    if max_amount is not None:
        base_query = base_query.filter(Transaction.amount <= max_amount)

    if source and source.strip() and source.lower() != "all":
        s_lower = source.strip().lower()
        if s_lower in ["cash", "manual"]:
            base_query = base_query.filter(
                or_(
                    Transaction.source == "cash",
                    Transaction.source == "manual",
                    Transaction.source.is_(None)
                )
            )
        elif s_lower == "phonepe":
            base_query = base_query.filter(Transaction.source == "phonepe")
        else:
            base_query = base_query.filter(Transaction.source == source.strip())

    # Calculate filtered aggregates
    aggregates = base_query.with_entities(
        func.count(Transaction.id).label("total_count"),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), 0).label("income_sum"),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), 0).label("expense_sum"),
    ).first()

    total_count = aggregates.total_count if aggregates else 0
    total_income = Decimal(str(aggregates.income_sum)) if aggregates else Decimal("0.00")
    total_expense = Decimal(str(aggregates.expense_sum)) if aggregates else Decimal("0.00")

    # Sorting
    if sort_by == "amount":
        order_col = Transaction.amount.desc() if sort_order == "desc" else Transaction.amount.asc()
    else:
        order_col = Transaction.transaction_date.desc() if sort_order == "desc" else Transaction.transaction_date.asc()

    # Pagination
    offset = (page - 1) * page_size
    items = (
        base_query
        .options(joinedload(Transaction.category))
        .order_by(order_col, Transaction.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return PaginatedTransactions(
        items=[TransactionResponse.model_validate(item) for item in items],
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_income=total_income,
        total_expense=total_expense
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    tx_in: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a new income or expense transaction."""
    category = db.query(Category).filter(
        Category.id == tx_in.category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified category does not exist."
        )

    # Validate category type suitability
    if category.type != CategoryType.BOTH and category.type.value != tx_in.type.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{category.name}' is an {category.type.value} category and cannot be used for {tx_in.type.value} transactions."
        )

    new_tx = Transaction(
        user_id=current_user.id,
        category_id=tx_in.category_id,
        type=tx_in.type,
        amount=tx_in.amount,
        description=tx_in.description.strip(),
        transaction_date=tx_in.transaction_date,
        source=tx_in.source or "manual",
        transaction_time=tx_in.transaction_time,
        external_transaction_id=tx_in.external_transaction_id,
        external_utr=tx_in.external_utr,
        source_reference=tx_in.source_reference
    )
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)

    # Check budget thresholds if expense
    if new_tx.type == TransactionType.EXPENSE:
        try:
            from app.services.scheduler_service import SchedulerService
            SchedulerService.check_budget_thresholds(db, current_user.id)
        except Exception:
            pass

    # Eager load category for response
    new_tx.category = category
    return new_tx


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve details of a specific transaction."""
    tx = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )
    return tx


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    tx_in: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing transaction."""
    tx = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    target_category_id = tx_in.category_id if tx_in.category_id is not None else tx.category_id
    target_type = tx_in.type if tx_in.type is not None else tx.type

    # Validate category if changed or type changed
    category = db.query(Category).filter(
        Category.id == target_category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified category does not exist."
        )

    if category.type != CategoryType.BOTH and category.type.value != target_type.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{category.name}' is an {category.type.value} category and cannot be used for {target_type.value} transactions."
        )

    if tx_in.category_id is not None:
        tx.category_id = tx_in.category_id
        tx.category = category
    if tx_in.type is not None:
        tx.type = tx_in.type
    if tx_in.amount is not None:
        tx.amount = tx_in.amount
    if tx_in.description is not None:
        tx.description = tx_in.description.strip()
    if tx_in.transaction_date is not None:
        tx.transaction_date = tx_in.transaction_date
    if tx_in.source is not None:
        tx.source = tx_in.source
    if tx_in.transaction_time is not None:
        tx.transaction_time = tx_in.transaction_time
    if tx_in.external_transaction_id is not None:
        tx.external_transaction_id = tx_in.external_transaction_id
    if tx_in.external_utr is not None:
        tx.external_utr = tx_in.external_utr
    if tx_in.source_reference is not None:
        tx.source_reference = tx_in.source_reference

    db.commit()
    db.refresh(tx)

    if tx.type == TransactionType.EXPENSE:
        try:
            from app.services.scheduler_service import SchedulerService
            SchedulerService.check_budget_thresholds(db, current_user.id)
        except Exception:
            pass

    return tx


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a transaction."""
    tx = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    db.delete(tx)
    db.commit()
    return {"message": "Transaction deleted successfully."}
