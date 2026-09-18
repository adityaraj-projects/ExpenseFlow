from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.recurring_transaction import (
    RecurringCreate,
    RecurringUpdate,
    RecurringResponse
)
from app.services.recurring_service import RecurringService
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/recurring-transactions", tags=["Recurring Transactions"])


@router.get("", response_model=List[RecurringResponse])
def get_recurring_transactions(
    status: Optional[str] = Query(None, description="Filter by status: active, paused, completed"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve recurring transactions for the authenticated user."""
    return RecurringService.get_recurring_list(db, current_user.id, status=status)


@router.post("", response_model=RecurringResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_transaction(
    data: RecurringCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new recurring transaction template."""
    return RecurringService.create_recurring(db, current_user.id, data)


@router.get("/{id}", response_model=RecurringResponse)
def get_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve a specific recurring transaction template by ID."""
    rec = RecurringService.get_recurring_by_id(db, current_user.id, id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring transaction not found")
    return rec


@router.put("/{id}", response_model=RecurringResponse)
def update_recurring_transaction(
    id: int,
    data: RecurringUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a recurring transaction template."""
    rec = RecurringService.update_recurring(db, current_user.id, id, data)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring transaction not found")
    return rec


@router.patch("/{id}/pause", response_model=RecurringResponse)
def pause_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause a recurring transaction."""
    rec = RecurringService.pause_recurring(db, current_user.id, id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring transaction not found")
    return rec


@router.patch("/{id}/resume", response_model=RecurringResponse)
def resume_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume an active recurring transaction."""
    rec = RecurringService.resume_recurring(db, current_user.id, id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring transaction not found")
    return rec


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a recurring transaction template."""
    success = RecurringService.delete_recurring(db, current_user.id, id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring transaction not found")
    return None


@router.post("/process-now")
def process_due_recurring_now(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger on-demand generation of any due occurrences for the authenticated user."""
    count = SchedulerService.process_due_recurring_transactions(db, current_user.id)
    return {"message": f"Processed successfully. {count} transaction(s) generated.", "generated_count": count}
