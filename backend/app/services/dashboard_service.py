from datetime import date, datetime
from decimal import Decimal
from typing import List
from calendar import month_abbr
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, extract
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal
from app.schemas.dashboard import (
    DashboardSummary,
    MonthlyTrendItem,
    CategoryBreakdownItem,
    DashboardData
)
from app.schemas.transaction import TransactionResponse
from app.schemas.budget import BudgetProgressResponse
from app.schemas.savings_goal import GoalResponse


class DashboardService:
    @staticmethod
    def get_dashboard_data(db: Session, user_id: int) -> DashboardData:
        today = date.today()
        current_year = today.year
        current_month = today.month

        # 1. All-time income & expense
        all_time = db.query(
            func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
        ).filter(Transaction.user_id == user_id).first()

        tot_income = Decimal(str(all_time.income)) if all_time else Decimal("0.00")
        tot_expense = Decimal(str(all_time.expense)) if all_time else Decimal("0.00")
        tot_balance = tot_income - tot_expense

        # 2. Current month income & expense
        month_agg = db.query(
            func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
        ).filter(
            Transaction.user_id == user_id,
            extract("year", Transaction.transaction_date) == current_year,
            extract("month", Transaction.transaction_date) == current_month
        ).first()

        m_income = Decimal(str(month_agg.income)) if month_agg else Decimal("0.00")
        m_expense = Decimal(str(month_agg.expense)) if month_agg else Decimal("0.00")

        # 3. Monthly Budget & Budget spent
        m_budget_scalar = db.query(
            func.coalesce(func.sum(Budget.amount), Decimal("0.00"))
        ).filter(
            Budget.user_id == user_id,
            Budget.year == current_year,
            Budget.month == current_month
        ).scalar()
        m_budget = Decimal(str(m_budget_scalar))

        # Calculate actual spending against budgeted categories
        budget_spent_scalar = db.query(
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            extract("year", Transaction.transaction_date) == current_year,
            extract("month", Transaction.transaction_date) == current_month,
            Transaction.category_id.in_(
                db.query(Budget.category_id).filter(
                    Budget.user_id == user_id,
                    Budget.year == current_year,
                    Budget.month == current_month
                )
            )
        ).scalar()
        m_budget_spent = Decimal(str(budget_spent_scalar))
        m_budget_remaining = max(Decimal("0.00"), m_budget - m_budget_spent)
        budget_pct = float(round((m_budget_spent / m_budget) * 100, 1)) if m_budget > 0 else 0.0

        # 4. Savings goals
        goals_agg = db.query(
            func.count(SavingsGoal.id).label("count"),
            func.coalesce(func.sum(SavingsGoal.current_amount), Decimal("0.00")).label("saved")
        ).filter(SavingsGoal.user_id == user_id).first()

        active_goals = goals_agg.count if goals_agg else 0
        total_saved_in_goals = Decimal(str(goals_agg.saved)) if goals_agg else Decimal("0.00")

        summary = DashboardSummary(
            total_balance=tot_balance,
            total_income=tot_income,
            total_expenses=tot_expense,
            net_savings=tot_balance,
            month_income=m_income,
            month_expense=m_expense,
            month_budget=m_budget,
            month_budget_spent=m_budget_spent,
            month_budget_remaining=m_budget_remaining,
            budget_percentage_used=budget_pct,
            active_goals_count=active_goals,
            total_saved_in_goals=total_saved_in_goals
        )

        # 5. Rolling 6-month trend (income vs expense)
        monthly_trend: List[MonthlyTrendItem] = []
        for i in range(5, -1, -1):
            # Calculate month and year for (current_month - i)
            m = current_month - i
            y = current_year
            while m <= 0:
                m += 12
                y -= 1

            trend_agg = db.query(
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                extract("year", Transaction.transaction_date) == y,
                extract("month", Transaction.transaction_date) == m
            ).first()

            inc = Decimal(str(trend_agg.income)) if trend_agg else Decimal("0.00")
            exp = Decimal(str(trend_agg.expense)) if trend_agg else Decimal("0.00")

            monthly_trend.append(
                MonthlyTrendItem(
                    period=f"{month_abbr[m]} {y}",
                    year=y,
                    month=m,
                    income=inc,
                    expense=exp,
                    net=inc - exp
                )
            )

        # 6. Current Month Category Breakdown (Expenses)
        cat_breakdown_raw = (
            db.query(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                Category.icon.label("category_icon"),
                Category.color.label("category_color"),
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("amount")
            )
            .join(Transaction, Transaction.category_id == Category.id)
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                extract("year", Transaction.transaction_date) == current_year,
                extract("month", Transaction.transaction_date) == current_month
            )
            .group_by(Category.id, Category.name, Category.icon, Category.color)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )

        total_cat_expense = sum((Decimal(str(r.amount)) for r in cat_breakdown_raw), Decimal("0.00"))
        category_breakdown: List[CategoryBreakdownItem] = []
        for r in cat_breakdown_raw:
            amt = Decimal(str(r.amount))
            pct = float(round((amt / total_cat_expense) * 100, 1)) if total_cat_expense > 0 else 0.0
            category_breakdown.append(
                CategoryBreakdownItem(
                    category_id=r.category_id,
                    category_name=r.category_name,
                    category_icon=r.category_icon,
                    category_color=r.category_color,
                    amount=amt,
                    percentage=pct
                )
            )

        # 7. Recent 5 transactions
        recent_txs = (
            db.query(Transaction)
            .options(joinedload(Transaction.category))
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .limit(5)
            .all()
        )

        # 8. Active budgets progress
        budgets_list = (
            db.query(Budget)
            .options(joinedload(Budget.category))
            .filter(
                Budget.user_id == user_id,
                Budget.month == current_month,
                Budget.year == current_year
            )
            .limit(4)
            .all()
        )

        # Category spending map for current month
        cat_spent_raw = (
            db.query(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("spent")
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                extract("year", Transaction.transaction_date) == current_year,
                extract("month", Transaction.transaction_date) == current_month
            )
            .group_by(Transaction.category_id)
            .all()
        )
        cat_spent_map = {r.category_id: Decimal(str(r.spent)) for r in cat_spent_raw}

        budget_progress: List[BudgetProgressResponse] = []
        for b in budgets_list:
            b_amt = Decimal(str(b.amount))
            sp = cat_spent_map.get(b.category_id, Decimal("0.00"))
            rem = b_amt - sp
            pct = float(round((sp / b_amt) * 100, 1)) if b_amt > 0 else 0.0
            status_str = "exceeded" if pct > 100.0 else ("warning" if pct >= 80.0 else "safe")
            budget_progress.append(
                BudgetProgressResponse(
                    id=b.id,
                    user_id=b.user_id,
                    category_id=b.category_id,
                    category_name=b.category.name if b.category else "Unknown",
                    category_icon=b.category.icon if b.category else "tag",
                    category_color=b.category.color if b.category else "#6366F1",
                    budget_amount=b_amt,
                    spent_amount=sp,
                    remaining_amount=rem,
                    percentage_used=pct,
                    month=b.month,
                    year=b.year,
                    status=status_str
                )
            )

        # 9. Savings goals
        goals_list = (
            db.query(SavingsGoal)
            .filter(SavingsGoal.user_id == user_id)
            .order_by(SavingsGoal.created_at.desc())
            .limit(4)
            .all()
        )
        goals_responses = []
        for g in goals_list:
            target = Decimal(str(g.target_amount))
            curr = Decimal(str(g.current_amount))
            pct = float(round((curr / target) * 100, 1)) if target > 0 else 0.0
            goals_responses.append(
                GoalResponse(
                    id=g.id,
                    user_id=g.user_id,
                    name=g.name,
                    target_amount=target,
                    current_amount=curr,
                    remaining_amount=max(Decimal("0.00"), target - curr),
                    progress_percentage=pct,
                    target_date=g.target_date,
                    description=g.description,
                    status=g.status,
                    created_at=g.created_at,
                    updated_at=g.updated_at
                )
            )

        # 10. Sync scheduled events idempotently & fetch upcoming items
        try:
            from app.services.scheduler_service import SchedulerService
            SchedulerService.sync_user_scheduled_events(db, user_id)
        except Exception:
            pass

        from app.models.reminder import Reminder, ReminderStatus
        from app.schemas.reminder import ReminderResponse
        from app.models.recurring_transaction import RecurringTransaction, RecurringStatus
        from app.schemas.recurring_transaction import RecurringResponse
        from app.services.notification_service import NotificationService

        upcoming_reminders_db = (
            db.query(Reminder)
            .filter(Reminder.user_id == user_id, Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]))
            .order_by(Reminder.reminder_date.asc())
            .limit(3)
            .all()
        )
        upcoming_recurring_db = (
            db.query(RecurringTransaction)
            .filter(RecurringTransaction.user_id == user_id, RecurringTransaction.status == RecurringStatus.ACTIVE)
            .order_by(RecurringTransaction.next_occurrence_date.asc())
            .limit(3)
            .all()
        )
        unread_notifs = NotificationService.get_unread_count(db, user_id)

        return DashboardData(
            summary=summary,
            monthly_trend=monthly_trend,
            category_breakdown=category_breakdown,
            recent_transactions=[TransactionResponse.model_validate(t) for t in recent_txs],
            budget_progress=budget_progress,
            savings_goals=goals_responses,
            upcoming_reminders=[ReminderResponse.model_validate(r) for r in upcoming_reminders_db],
            upcoming_recurring=[RecurringResponse.model_validate(rec) for rec in upcoming_recurring_db],
            unread_notifications_count=unread_notifs
        )

