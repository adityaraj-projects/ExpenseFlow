from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal
from app.models.reminder import Reminder
from app.models.recurring_transaction import RecurringTransaction
from app.models.notification import Notification
from app.models.statement_import import StatementImport
from app.schemas.user import DeleteFinancialDataRequest, DeleteFinancialDataResponse

router = APIRouter(prefix="/users", tags=["Users & Data Management"])


@router.delete("/financial-data", response_model=DeleteFinancialDataResponse)
def delete_financial_data(
    req: DeleteFinancialDataRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete all financial data belonging to the authenticated user.
    Strictly scoped to current_user.id from verified JWT token.
    Preserves user account, profile, and default categories.
    Rolls back completely if any failure occurs midway.
    """
    if req.confirmation.strip() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation string must be exactly 'DELETE'."
        )

    user_id = current_user.id

    try:
        # Pre-count owned records for reporting
        tx_count = db.query(Transaction).filter(Transaction.user_id == user_id).count()
        bg_count = db.query(Budget).filter(Budget.user_id == user_id).count()
        sg_count = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).count()
        rm_count = db.query(Reminder).filter(Reminder.user_id == user_id).count()
        rc_count = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user_id).count()
        nt_count = db.query(Notification).filter(Notification.user_id == user_id).count()
        si_count = db.query(StatementImport).filter(StatementImport.user_id == user_id).count()

        # Cascade / explicit removal in FK-safe dependency order
        db.query(Transaction).filter(Transaction.user_id == user_id).delete(synchronize_session=False)
        db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user_id).delete(synchronize_session=False)
        db.query(Reminder).filter(Reminder.user_id == user_id).delete(synchronize_session=False)
        db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).delete(synchronize_session=False)
        db.query(Budget).filter(Budget.user_id == user_id).delete(synchronize_session=False)
        db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
        db.query(StatementImport).filter(StatementImport.user_id == user_id).delete(synchronize_session=False)

        db.commit()

        return DeleteFinancialDataResponse(
            message="Financial data successfully deleted.",
            deleted_transactions=tx_count,
            deleted_budgets=bg_count,
            deleted_goals=sg_count,
            deleted_reminders=rm_count,
            deleted_recurring=rc_count,
            deleted_notifications=nt_count,
            deleted_statement_imports=si_count
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete financial data: {str(e)}"
        )
