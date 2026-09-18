import calendar
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.models.reminder import Reminder, ReminderRecurrence, ReminderStatus
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderService:

    @staticmethod
    def calculate_next_date(current_date: date, recurrence: ReminderRecurrence) -> Optional[date]:
        """
        Calculates next reminder date handling variable month lengths safely (28, 30, 31 days).
        """
        if recurrence == ReminderRecurrence.ONCE:
            return None
        elif recurrence == ReminderRecurrence.DAILY:
            return current_date + timedelta(days=1)
        elif recurrence == ReminderRecurrence.WEEKLY:
            return current_date + timedelta(days=7)
        elif recurrence == ReminderRecurrence.MONTHLY:
            year = current_date.year + (current_date.month // 12)
            month = (current_date.month % 12) + 1
            max_days = calendar.monthrange(year, month)[1]
            day = min(current_date.day, max_days)
            return date(year, month, day)
        elif recurrence == ReminderRecurrence.YEARLY:
            year = current_date.year + 1
            month = current_date.month
            max_days = calendar.monthrange(year, month)[1]
            day = min(current_date.day, max_days)
            return date(year, month, day)
        return None

    @classmethod
    def get_reminders(
        cls,
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Reminder]:
        query = db.query(Reminder).filter(Reminder.user_id == user_id)
        if status:
            if status == "upcoming":
                query = query.filter(Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]))
            elif status in [s.value for s in ReminderStatus]:
                query = query.filter(Reminder.status == status)
        if search:
            query = query.filter(
                or_(
                    Reminder.title.ilike(f"%{search}%"),
                    Reminder.description.ilike(f"%{search}%")
                )
            )
        return query.order_by(Reminder.reminder_date.asc(), Reminder.id.asc()).all()

    @classmethod
    def get_reminder_by_id(cls, db: Session, user_id: int, reminder_id: int) -> Optional[Reminder]:
        return db.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id
        ).first()

    @classmethod
    def create_reminder(cls, db: Session, user_id: int, data: ReminderCreate) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            amount=data.amount,
            reminder_date=data.reminder_date,
            reminder_time=data.reminder_time,
            recurrence=data.recurrence,
            notification_enabled=data.notification_enabled,
            status=ReminderStatus.PENDING
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    @classmethod
    def update_reminder(
        cls,
        db: Session,
        user_id: int,
        reminder_id: int,
        data: ReminderUpdate
    ) -> Optional[Reminder]:
        reminder = cls.get_reminder_by_id(db, user_id, reminder_id)
        if not reminder:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reminder, field, value)

        db.commit()
        db.refresh(reminder)
        return reminder

    @classmethod
    def complete_reminder(cls, db: Session, user_id: int, reminder_id: int) -> Optional[Reminder]:
        reminder = cls.get_reminder_by_id(db, user_id, reminder_id)
        if not reminder:
            return None

        if reminder.recurrence != ReminderRecurrence.ONCE:
            next_d = cls.calculate_next_date(reminder.reminder_date, reminder.recurrence)
            if next_d:
                reminder.reminder_date = next_d
                reminder.status = ReminderStatus.PENDING
            else:
                reminder.status = ReminderStatus.COMPLETED
        else:
            reminder.status = ReminderStatus.COMPLETED

        db.commit()
        db.refresh(reminder)
        return reminder

    @classmethod
    def snooze_reminder(cls, db: Session, user_id: int, reminder_id: int, days: int = 1) -> Optional[Reminder]:
        reminder = cls.get_reminder_by_id(db, user_id, reminder_id)
        if not reminder:
            return None

        reminder.reminder_date = reminder.reminder_date + timedelta(days=days)
        reminder.status = ReminderStatus.SNOOZED
        db.commit()
        db.refresh(reminder)
        return reminder

    @classmethod
    def delete_reminder(cls, db: Session, user_id: int, reminder_id: int) -> bool:
        reminder = cls.get_reminder_by_id(db, user_id, reminder_id)
        if not reminder:
            return False
        db.delete(reminder)
        db.commit()
        return True
