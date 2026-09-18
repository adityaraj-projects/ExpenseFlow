from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.reminder import Reminder, ReminderStatus
from app.models.recurring_transaction import RecurringTransaction, RecurringStatus
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.models.savings_goal import SavingsGoal, GoalStatus
from app.models.notification import NotificationType
from app.services.reminder_service import ReminderService
from app.services.recurring_service import RecurringService
from app.services.notification_service import NotificationService


class SchedulerService:

    @classmethod
    def process_due_reminders(cls, db: Session, user_id: Optional[int] = None) -> int:
        today = date.today()
        query = db.query(Reminder).filter(
            Reminder.reminder_date <= today,
            Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
            Reminder.notification_enabled == True
        )
        if user_id:
            query = query.filter(Reminder.user_id == user_id)

        due_reminders = query.all()
        notified_count = 0

        for r in due_reminders:
            idempotency_key = f"reminder_due_{r.id}_{r.reminder_date.isoformat()}"
            amt_str = f" for ₹{r.amount:.2f}" if r.amount else ""
            notif = NotificationService.create_notification(
                db=db,
                user_id=r.user_id,
                title=f"Reminder: {r.title}",
                message=f"Your scheduled reminder '{r.title}'{amt_str} is due.",
                notification_type=NotificationType.REMINDER,
                reference_id=r.id,
                idempotency_key=idempotency_key
            )
            if notif:
                notified_count += 1

        return notified_count

    @classmethod
    def process_due_recurring_transactions(cls, db: Session, user_id: Optional[int] = None) -> int:
        today = date.today()
        query = db.query(RecurringTransaction).filter(
            RecurringTransaction.next_occurrence_date <= today,
            RecurringTransaction.status == RecurringStatus.ACTIVE
        )
        if user_id:
            query = query.filter(RecurringTransaction.user_id == user_id)

        due_recurring = query.all()
        generated_count = 0

        for rec in due_recurring:
            occ_date = rec.next_occurrence_date
            trans = RecurringService.generate_occurrence(db, rec, occ_date)
            if trans:
                generated_count += 1
                idempotency_key = f"recurring_gen_{rec.id}_{occ_date.isoformat()}"
                NotificationService.create_notification(
                    db=db,
                    user_id=rec.user_id,
                    title="Recurring Transaction Created",
                    message=f"Recurring {rec.type} '{rec.description}' (₹{rec.amount:.2f}) was recorded for {occ_date.strftime('%d %b %Y')}.",
                    notification_type=NotificationType.RECURRING_GENERATED,
                    reference_id=trans.id,
                    idempotency_key=idempotency_key
                )

        return generated_count

    @classmethod
    def check_budget_thresholds(cls, db: Session, user_id: Optional[int] = None) -> int:
        today = date.today()
        month = today.month
        year = today.year

        query = db.query(Budget).filter(
            Budget.month == month,
            Budget.year == year
        )
        if user_id:
            query = query.filter(Budget.user_id == user_id)

        budgets = query.all()
        alerts_created = 0

        for b in budgets:
            # Calculate spent amount in this category for current month
            start_date = date(year, month, 1)
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            end_date = date(next_year, next_month, 1)

            spent = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
                Transaction.user_id == b.user_id,
                Transaction.category_id == b.category_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date < end_date
            ).scalar()

            if b.amount > 0:
                pct = (spent / b.amount) * 100
                cat_name = b.category.name if b.category else "Category"

                if pct >= 100:
                    idempotency_key = f"budget_100_{b.id}_{month}_{year}"
                    notif = NotificationService.create_notification(
                        db=db,
                        user_id=b.user_id,
                        title=f"Budget Exceeded: {cat_name}",
                        message=f"You have spent ₹{spent:.2f} of your ₹{b.amount:.2f} limit ({pct:.0f}%) for {cat_name}.",
                        notification_type=NotificationType.BUDGET_EXCEEDED,
                        reference_id=b.id,
                        idempotency_key=idempotency_key
                    )
                    if notif:
                        alerts_created += 1
                elif pct >= 80:
                    idempotency_key = f"budget_80_{b.id}_{month}_{year}"
                    notif = NotificationService.create_notification(
                        db=db,
                        user_id=b.user_id,
                        title=f"Budget Warning: {cat_name}",
                        message=f"You have used {pct:.0f}% of your {cat_name} budget (₹{spent:.2f} / ₹{b.amount:.2f}).",
                        notification_type=NotificationType.BUDGET_WARNING,
                        reference_id=b.id,
                        idempotency_key=idempotency_key
                    )
                    if notif:
                        alerts_created += 1

        return alerts_created

    @classmethod
    def check_savings_deadlines(cls, db: Session, user_id: Optional[int] = None) -> int:
        today = date.today()
        soon = today + timedelta(days=3)

        query = db.query(SavingsGoal).filter(
            SavingsGoal.status == GoalStatus.IN_PROGRESS,
            SavingsGoal.target_date != None,
            SavingsGoal.target_date <= soon
        )
        if user_id:
            query = query.filter(SavingsGoal.user_id == user_id)

        goals = query.all()
        alerts_created = 0

        for g in goals:
            idempotency_key = f"goal_deadline_{g.id}_{g.target_date.isoformat()}"
            diff_days = (g.target_date - today).days
            timing_str = "today" if diff_days <= 0 else f"in {diff_days} days"

            notif = NotificationService.create_notification(
                db=db,
                user_id=g.user_id,
                title=f"Savings Goal Deadline: {g.name}",
                message=f"Goal '{g.name}' is due {timing_str}. Current progress: ₹{g.current_amount:.2f} / ₹{g.target_amount:.2f}.",
                notification_type=NotificationType.GOAL_DEADLINE,
                reference_id=g.id,
                idempotency_key=idempotency_key
            )
            if notif:
                alerts_created += 1

        return alerts_created

    @classmethod
    def sync_user_scheduled_events(cls, db: Session, user_id: int) -> Dict[str, int]:
        """
        Idempotent per-user event sync called when user loads their dashboard.
        Guarantees users see up-to-date reminders, recurring items, and alerts instantly.
        """
        reminders = cls.process_due_reminders(db, user_id)
        recurring = cls.process_due_recurring_transactions(db, user_id)
        budgets = cls.check_budget_thresholds(db, user_id)
        goals = cls.check_savings_deadlines(db, user_id)
        return {
            "reminders_notified": reminders,
            "recurring_generated": recurring,
            "budget_alerts": budgets,
            "goal_alerts": goals
        }

    @classmethod
    def process_all_scheduled_events(cls, db: Session) -> Dict[str, int]:
        """
        Global scheduler run invoked by standalone worker / cron daemon.
        """
        reminders = cls.process_due_reminders(db)
        recurring = cls.process_due_recurring_transactions(db)
        budgets = cls.check_budget_thresholds(db)
        goals = cls.check_savings_deadlines(db)
        return {
            "reminders_notified": reminders,
            "recurring_generated": recurring,
            "budget_alerts": budgets,
            "goal_alerts": goals
        }
