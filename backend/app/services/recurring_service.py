import calendar
from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurringFrequency,
    RecurringStatus,
    RecurringTransactionType
)
from app.models.transaction import Transaction
from app.schemas.recurring_transaction import RecurringCreate, RecurringUpdate


class RecurringService:

    @staticmethod
    def calculate_next_date(current_date: date, frequency: RecurringFrequency) -> date:
        """
        Calculates next occurrence date with safe calendar boundary clamping (e.g. 31 Jan -> 28 Feb).
        """
        if frequency == RecurringFrequency.DAILY:
            return current_date + timedelta(days=1)
        elif frequency == RecurringFrequency.WEEKLY:
            return current_date + timedelta(days=7)
        elif frequency == RecurringFrequency.MONTHLY:
            year = current_date.year + (current_date.month // 12)
            month = (current_date.month % 12) + 1
            max_days = calendar.monthrange(year, month)[1]
            day = min(current_date.day, max_days)
            return date(year, month, day)
        elif frequency == RecurringFrequency.YEARLY:
            year = current_date.year + 1
            month = current_date.month
            max_days = calendar.monthrange(year, month)[1]
            day = min(current_date.day, max_days)
            return date(year, month, day)
        return current_date + timedelta(days=30)

    @classmethod
    def get_recurring_list(
        cls,
        db: Session,
        user_id: int,
        status: Optional[str] = None
    ) -> List[RecurringTransaction]:
        query = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user_id)
        if status and status in [s.value for s in RecurringStatus]:
            query = query.filter(RecurringTransaction.status == status)
        return query.order_by(RecurringTransaction.next_occurrence_date.asc(), RecurringTransaction.id.asc()).all()

    @classmethod
    def get_recurring_by_id(
        cls,
        db: Session,
        user_id: int,
        recurring_id: int
    ) -> Optional[RecurringTransaction]:
        return db.query(RecurringTransaction).filter(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == user_id
        ).first()

    @classmethod
    def create_recurring(
        cls,
        db: Session,
        user_id: int,
        data: RecurringCreate
    ) -> RecurringTransaction:
        recurring = RecurringTransaction(
            user_id=user_id,
            category_id=data.category_id,
            type=data.type,
            amount=data.amount,
            description=data.description,
            payment_method=data.payment_method,
            frequency=data.frequency,
            start_date=data.start_date,
            next_occurrence_date=data.start_date,
            status=RecurringStatus.ACTIVE
        )
        db.add(recurring)
        db.commit()
        db.refresh(recurring)
        return recurring

    @classmethod
    def update_recurring(
        cls,
        db: Session,
        user_id: int,
        recurring_id: int,
        data: RecurringUpdate
    ) -> Optional[RecurringTransaction]:
        recurring = cls.get_recurring_by_id(db, user_id, recurring_id)
        if not recurring:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(recurring, field, value)

        db.commit()
        db.refresh(recurring)
        return recurring

    @classmethod
    def pause_recurring(cls, db: Session, user_id: int, recurring_id: int) -> Optional[RecurringTransaction]:
        recurring = cls.get_recurring_by_id(db, user_id, recurring_id)
        if not recurring:
            return None
        recurring.status = RecurringStatus.PAUSED
        db.commit()
        db.refresh(recurring)
        return recurring

    @classmethod
    def resume_recurring(cls, db: Session, user_id: int, recurring_id: int) -> Optional[RecurringTransaction]:
        recurring = cls.get_recurring_by_id(db, user_id, recurring_id)
        if not recurring:
            return None
        recurring.status = RecurringStatus.ACTIVE
        db.commit()
        db.refresh(recurring)
        return recurring

    @classmethod
    def delete_recurring(cls, db: Session, user_id: int, recurring_id: int) -> bool:
        recurring = cls.get_recurring_by_id(db, user_id, recurring_id)
        if not recurring:
            return False
        db.delete(recurring)
        db.commit()
        return True

    @classmethod
    def generate_occurrence(
        cls,
        db: Session,
        recurring: RecurringTransaction,
        target_date: Optional[date] = None
    ) -> Optional[Transaction]:
        """
        Idempotently generates a transaction for the given recurring template.
        Guarantees that a transaction is never created twice for the same occurrence date.
        """
        occurrence_date = target_date or recurring.next_occurrence_date

        # Idempotency check: does a transaction for this recurring template on this date already exist?
        existing = db.query(Transaction).filter(
            Transaction.recurring_transaction_id == recurring.id,
            Transaction.transaction_date == occurrence_date
        ).first()

        if existing:
            # Advance next_occurrence_date if it hasn't caught up
            if recurring.next_occurrence_date <= occurrence_date:
                recurring.next_occurrence_date = cls.calculate_next_date(occurrence_date, recurring.frequency)
                db.commit()
            return existing

        # Create the transaction
        new_transaction = Transaction(
            user_id=recurring.user_id,
            category_id=recurring.category_id,
            type=recurring.type,
            amount=recurring.amount,
            description=f"{recurring.description} (Auto)",
            transaction_date=occurrence_date,
            recurring_transaction_id=recurring.id
        )
        db.add(new_transaction)

        # Update recurring metadata
        recurring.last_generated_date = occurrence_date
        recurring.next_occurrence_date = cls.calculate_next_date(occurrence_date, recurring.frequency)

        db.commit()
        db.refresh(new_transaction)
        db.refresh(recurring)
        return new_transaction
