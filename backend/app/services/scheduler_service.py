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
    def process_upcoming_reminders(cls, db: Session, user_id: Optional[int] = None) -> int:
        """Alerts users for bills / reminders due tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        query = db.query(Reminder).filter(
            Reminder.reminder_date == tomorrow,
            Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
            Reminder.notification_enabled == True
        )
        if user_id:
            query = query.filter(Reminder.user_id == user_id)

        upcoming_reminders = query.all()
        notified_count = 0

        for r in upcoming_reminders:
            idempotency_key = f"reminder_upcoming_{r.id}_{r.reminder_date.isoformat()}"
            amt_str = f" of ₹{r.amount:.2f}" if r.amount else ""
            notif = NotificationService.create_notification(
                db=db,
                user_id=r.user_id,
                title=f"Upcoming Bill: {r.title}",
                message=f"🔔 '{r.title}'{amt_str} is due tomorrow ({r.reminder_date.strftime('%d %b')}).",
                notification_type=NotificationType.REMINDER,
                reference_id=r.id,
                idempotency_key=idempotency_key
            )
            if notif:
                notified_count += 1

        return notified_count

    @classmethod
    def process_upcoming_recurring_transactions(cls, db: Session, user_id: Optional[int] = None) -> int:
        """Notifies users of recurring transactions scheduled for tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        query = db.query(RecurringTransaction).filter(
            RecurringTransaction.next_occurrence_date == tomorrow,
            RecurringTransaction.status == RecurringStatus.ACTIVE
        )
        if user_id:
            query = query.filter(RecurringTransaction.user_id == user_id)

        upcoming_rec = query.all()
        notified_count = 0

        for rec in upcoming_rec:
            idempotency_key = f"recurring_upcoming_{rec.id}_{rec.next_occurrence_date.isoformat()}"
            notif = NotificationService.create_notification(
                db=db,
                user_id=rec.user_id,
                title=f"Upcoming Recurring Expense",
                message=f"🔄 Recurring {rec.type} '{rec.description}' (₹{rec.amount:.2f}) is scheduled for tomorrow.",
                notification_type=NotificationType.RECURRING_UPCOMING,
                reference_id=rec.id,
                idempotency_key=idempotency_key
            )
            if notif:
                notified_count += 1

        return notified_count

    @classmethod
    def check_monthly_summary_notification(cls, db: Session, user_id: Optional[int] = None) -> int:
        """Sends monthly financial summary notification for the previous month."""
        today = date.today()
        # Previous month
        first_this_month = date(today.year, today.month, 1)
        last_day_prev = first_this_month - timedelta(days=1)
        prev_month = last_day_prev.month
        prev_year = last_day_prev.year
        start_prev = date(prev_year, prev_month, 1)

        import calendar
        month_name = calendar.month_name[prev_month]

        # Target users
        from app.models.user import User
        user_query = db.query(User.id)
        if user_id:
            user_query = user_query.filter(User.id == user_id)
        users = [u[0] for u in user_query.all()]

        notified_count = 0
        for uid in users:
            idempotency_key = f"monthly_summary_{uid}_{prev_year}_{prev_month:02d}"

            # Check if transactions exist in previous month
            inc = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
                Transaction.user_id == uid,
                Transaction.type == TransactionType.INCOME,
                Transaction.transaction_date >= start_prev,
                Transaction.transaction_date <= last_day_prev
            ).scalar()

            exp = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
                Transaction.user_id == uid,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_prev,
                Transaction.transaction_date <= last_day_prev
            ).scalar()

            if inc > 0 or exp > 0:
                saved = inc - exp
                rate = ((saved / inc) * 100) if inc > 0 else 0.0
                notif = NotificationService.create_notification(
                    db=db,
                    user_id=uid,
                    title=f"📊 {month_name} Summary",
                    message=f"Income: ₹{inc:,.2f} • Expenses: ₹{exp:,.2f} • Saved: ₹{saved:,.2f} ({rate:.0f}% savings rate).",
                    notification_type=NotificationType.MONTHLY_SUMMARY,
                    idempotency_key=idempotency_key
                )
                if notif:
                    notified_count += 1

        return notified_count

    @classmethod
    def sync_user_scheduled_events(cls, db: Session, user_id: int) -> Dict[str, int]:
        """
        Idempotent per-user event sync called when user loads their dashboard.
        Guarantees users see up-to-date reminders, recurring items, and alerts instantly.
        """
        reminders = cls.process_due_reminders(db, user_id)
        upcoming_reminders = cls.process_upcoming_reminders(db, user_id)
        recurring = cls.process_due_recurring_transactions(db, user_id)
        upcoming_recurring = cls.process_upcoming_recurring_transactions(db, user_id)
        budgets = cls.check_budget_thresholds(db, user_id)
        goals = cls.check_savings_deadlines(db, user_id)
        monthly_summary = cls.check_monthly_summary_notification(db, user_id)
        return {
            "reminders_notified": reminders + upcoming_reminders,
            "recurring_generated": recurring + upcoming_recurring,
            "budget_alerts": budgets,
            "goal_alerts": goals,
            "monthly_summary": monthly_summary
        }

    @classmethod
    def process_all_scheduled_events(cls, db: Session) -> Dict[str, int]:
        """
        Global scheduler run invoked by standalone worker / cron daemon.
        """
        reminders = cls.process_due_reminders(db)
        upcoming_reminders = cls.process_upcoming_reminders(db)
        recurring = cls.process_due_recurring_transactions(db)
        upcoming_recurring = cls.process_upcoming_recurring_transactions(db)
        budgets = cls.check_budget_thresholds(db)
        goals = cls.check_savings_deadlines(db)
        monthly_summary = cls.check_monthly_summary_notification(db)
        return {
            "reminders_notified": reminders + upcoming_reminders,
            "recurring_generated": recurring + upcoming_recurring,
            "budget_alerts": budgets,
            "goal_alerts": goals,
            "monthly_summary": monthly_summary
        }
