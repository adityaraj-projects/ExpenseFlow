from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderSnooze,
    ReminderResponse
)
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("", response_model=List[ReminderResponse])
def get_reminders(
    status: Optional[str] = Query(None, description="Filter by status: upcoming, pending, completed, snoozed"),
    search: Optional[str] = Query(None, description="Search by title or description"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all reminders for the authenticated user."""
    return ReminderService.get_reminders(db, current_user.id, status=status, search=search)


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    data: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new financial reminder."""
    return ReminderService.create_reminder(db, current_user.id, data)


@router.get("/{id}", response_model=ReminderResponse)
def get_reminder(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve a specific reminder by ID."""
    reminder = ReminderService.get_reminder_by_id(db, current_user.id, id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.put("/{id}", response_model=ReminderResponse)
def update_reminder(
    id: int,
    data: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing reminder."""
    reminder = ReminderService.update_reminder(db, current_user.id, id, data)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.patch("/{id}/complete", response_model=ReminderResponse)
def complete_reminder(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark reminder as completed (advances to next date if recurring)."""
    reminder = ReminderService.complete_reminder(db, current_user.id, id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.patch("/{id}/snooze", response_model=ReminderResponse)
def snooze_reminder(
    id: int,
    data: ReminderSnooze = ReminderSnooze(days=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Snooze reminder by specified number of days."""
    reminder = ReminderService.snooze_reminder(db, current_user.id, id, days=data.days)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a reminder."""
    success = ReminderService.delete_reminder(db, current_user.id, id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return None
