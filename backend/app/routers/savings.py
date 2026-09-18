from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.savings_goal import SavingsGoal, GoalStatus
from app.schemas.savings_goal import (
    GoalCreate,
    GoalUpdate,
    GoalDepositRequest,
    GoalResponse
)

router = APIRouter(prefix="/goals", tags=["Savings Goals"])


def _build_goal_response(goal: SavingsGoal) -> GoalResponse:
    target = Decimal(str(goal.target_amount))
    current = Decimal(str(goal.current_amount))
    remaining = max(Decimal("0.00"), target - current)
    pct = float(round((current / target) * 100, 1)) if target > 0 else 0.0

    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        name=goal.name,
        target_amount=target,
        current_amount=current,
        remaining_amount=remaining,
        progress_percentage=pct,
        target_date=goal.target_date,
        description=goal.description,
        status=goal.status,
        created_at=goal.created_at,
        updated_at=goal.updated_at
    )


@router.get("", response_model=List[GoalResponse])
def get_goals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all savings goals for the current user."""
    goals = (
        db.query(SavingsGoal)
        .filter(SavingsGoal.user_id == current_user.id)
        .order_by(SavingsGoal.created_at.desc())
        .all()
    )
    return [_build_goal_response(g) for g in goals]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    goal_in: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new savings goal."""
    initial = goal_in.initial_amount or Decimal("0.00")
    if initial > goal_in.target_amount:
        status_val = GoalStatus.COMPLETED
    else:
        status_val = GoalStatus.IN_PROGRESS

    new_goal = SavingsGoal(
        user_id=current_user.id,
        name=goal_in.name.strip(),
        target_amount=goal_in.target_amount,
        current_amount=initial,
        target_date=goal_in.target_date,
        description=goal_in.description.strip() if goal_in.description else None,
        status=status_val
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return _build_goal_response(new_goal)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve a single savings goal."""
    goal = db.query(SavingsGoal).filter(
        SavingsGoal.id == goal_id,
        SavingsGoal.user_id == current_user.id
    ).first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Savings goal not found."
        )
    return _build_goal_response(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    goal_in: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update goal properties."""
    goal = db.query(SavingsGoal).filter(
        SavingsGoal.id == goal_id,
        SavingsGoal.user_id == current_user.id
    ).first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Savings goal not found."
        )

    if goal_in.name is not None:
        goal.name = goal_in.name.strip()
    if goal_in.target_amount is not None:
        goal.target_amount = goal_in.target_amount
    if goal_in.target_date is not None:
        goal.target_date = goal_in.target_date
    if goal_in.description is not None:
        goal.description = goal_in.description.strip()
    if goal_in.status is not None:
        goal.status = goal_in.status
    else:
        # Auto recalculate status
        if goal.current_amount >= goal.target_amount:
            goal.status = GoalStatus.COMPLETED
        else:
            goal.status = GoalStatus.IN_PROGRESS

    db.commit()
    db.refresh(goal)
    return _build_goal_response(goal)


@router.post("/{goal_id}/deposit", response_model=GoalResponse)
def adjust_funds(
    goal_id: int,
    deposit_in: GoalDepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add or withdraw funds from a savings goal."""
    goal = db.query(SavingsGoal).filter(
        SavingsGoal.id == goal_id,
        SavingsGoal.user_id == current_user.id
    ).first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Savings goal not found."
        )

    current = Decimal(str(goal.current_amount))
    amount = deposit_in.amount

    if deposit_in.action == "withdraw":
        if amount > current:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot withdraw {amount}. Current savings balance is {current}."
            )
        goal.current_amount = current - amount
    else:  # deposit
        goal.current_amount = current + amount

    # Automatically update goal completion status
    if goal.current_amount >= goal.target_amount:
        goal.status = GoalStatus.COMPLETED
    else:
        goal.status = GoalStatus.IN_PROGRESS

    db.commit()
    db.refresh(goal)
    return _build_goal_response(goal)


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a savings goal."""
    goal = db.query(SavingsGoal).filter(
        SavingsGoal.id == goal_id,
        SavingsGoal.user_id == current_user.id
    ).first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Savings goal not found."
        )

    db.delete(goal)
    db.commit()
    return {"message": "Savings goal deleted successfully."}
