from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Tuple, List, Optional
import calendar
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category
from app.schemas.report import (
    ReportSummary,
    ReportTimeSeriesItem,
    ReportCategoryStatItem,
    ComprehensiveReport
)


class ReportService:
    @staticmethod
    def resolve_dates(
        timeframe: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Tuple[date, date]:
        today = date.today()

        if timeframe == "this_week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif timeframe == "this_month":
            start = date(today.year, today.month, 1)
            _, last_day = calendar.monthrange(today.year, today.month)
            end = date(today.year, today.month, last_day)
        elif timeframe == "last_month":
            first_this_month = date(today.year, today.month, 1)
            last_day_prev = first_this_month - timedelta(days=1)
            start = date(last_day_prev.year, last_day_prev.month, 1)
            end = last_day_prev
        elif timeframe == "this_year":
            start = date(today.year, 1, 1)
            end = date(today.year, 12, 31)
        elif timeframe == "custom" and start_date and end_date:
            start = start_date
            end = end_date
        else:  # default to this_month
            start = date(today.year, today.month, 1)
            _, last_day = calendar.monthrange(today.year, today.month)
            end = date(today.year, today.month, last_day)

        if start > end:
            start, end = end, start

        return start, end

    @staticmethod
    def generate_report(
        db: Session,
        user_id: int,
        timeframe: str = "this_month",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ComprehensiveReport:
        start, end = ReportService.resolve_dates(timeframe, start_date, end_date)
        days_span = max(1, (end - start).days + 1)

        # 1. Summary aggregations
        summary_raw = db.query(
            func.count(Transaction.id).label("tx_count"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end
        ).first()

        total_inc = Decimal(str(summary_raw.income)) if summary_raw else Decimal("0.00")
        total_exp = Decimal(str(summary_raw.expense)) if summary_raw else Decimal("0.00")
        tx_count = summary_raw.tx_count if summary_raw else 0
        net_savings = total_inc - total_exp
        savings_rate = float(round((net_savings / total_inc) * 100, 1)) if total_inc > 0 else 0.0
        daily_avg = Decimal(str(round(total_exp / Decimal(str(days_span)), 2)))

        summary = ReportSummary(
            start_date=start,
            end_date=end,
            total_income=total_inc,
            total_expense=total_exp,
            net_savings=net_savings,
            savings_rate=savings_rate,
            transaction_count=tx_count,
            daily_average_expense=daily_avg
        )

        # 2. Time series grouping
        time_series: List[ReportTimeSeriesItem] = []

        if timeframe == "this_week" or (timeframe == "custom" and days_span <= 14):
            # Group daily with weekday (e.g. "Mon 14", "Tue 15")
            daily_raw = db.query(
                Transaction.transaction_date.label("dt"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            ).group_by(Transaction.transaction_date).all()

            daily_map = {r.dt: (Decimal(str(r.income)), Decimal(str(r.expense))) for r in daily_raw}

            curr = start
            while curr <= end:
                inc, exp = daily_map.get(curr, (Decimal("0.00"), Decimal("0.00")))
                time_series.append(
                    ReportTimeSeriesItem(
                        date_label=curr.strftime("%a %d"),
                        exact_date=curr.strftime("%A, %d %B %Y"),
                        income=inc,
                        expense=exp,
                        net=inc - exp
                    )
                )
                curr += timedelta(days=1)

        elif timeframe in ["this_month", "last_month"] or (timeframe == "custom" and days_span <= 62):
            # Group daily with date and month (e.g. "01 Sep", "02 Sep")
            daily_raw = db.query(
                Transaction.transaction_date.label("dt"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            ).group_by(Transaction.transaction_date).all()

            daily_map = {r.dt: (Decimal(str(r.income)), Decimal(str(r.expense))) for r in daily_raw}

            curr = start
            while curr <= end:
                inc, exp = daily_map.get(curr, (Decimal("0.00"), Decimal("0.00")))
                time_series.append(
                    ReportTimeSeriesItem(
                        date_label=curr.strftime("%d %b"),
                        exact_date=curr.strftime("%d %B %Y"),
                        income=inc,
                        expense=exp,
                        net=inc - exp
                    )
                )
                curr += timedelta(days=1)

        elif timeframe == "this_year":
            # Group all 12 calendar months for the current year
            monthly_raw = db.query(
                extract("month", Transaction.transaction_date).label("mo"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            ).group_by(extract("month", Transaction.transaction_date)).all()

            month_map = {int(r.mo): (Decimal(str(r.income)), Decimal(str(r.expense))) for r in monthly_raw}

            for m in range(1, 13):
                inc, exp = month_map.get(m, (Decimal("0.00"), Decimal("0.00")))
                time_series.append(
                    ReportTimeSeriesItem(
                        date_label=calendar.month_abbr[m],
                        exact_date=f"{calendar.month_name[m]} {start.year}",
                        income=inc,
                        expense=exp,
                        net=inc - exp
                    )
                )

        else:
            # Custom range > 62 days
            if days_span <= 366:
                # Group monthly across the custom range
                monthly_raw = db.query(
                    extract("year", Transaction.transaction_date).label("yr"),
                    extract("month", Transaction.transaction_date).label("mo"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
                ).filter(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end
                ).group_by(
                    extract("year", Transaction.transaction_date),
                    extract("month", Transaction.transaction_date)
                ).all()

                month_map = {(int(r.yr), int(r.mo)): (Decimal(str(r.income)), Decimal(str(r.expense))) for r in monthly_raw}

                # Iterate month by month from start to end
                curr_y, curr_m = start.year, start.month
                end_y, end_m = end.year, end.month

                while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
                    inc, exp = month_map.get((curr_y, curr_m), (Decimal("0.00"), Decimal("0.00")))
                    time_series.append(
                        ReportTimeSeriesItem(
                            date_label=f"{calendar.month_abbr[curr_m]} {str(curr_y)[2:]}",
                            exact_date=f"{calendar.month_name[curr_m]} {curr_y}",
                            income=inc,
                            expense=exp,
                            net=inc - exp
                        )
                    )
                    curr_m += 1
                    if curr_m > 12:
                        curr_m = 1
                        curr_y += 1
            else:
                # Multi-year custom range -> Group yearly
                yearly_raw = db.query(
                    extract("year", Transaction.transaction_date).label("yr"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
                ).filter(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end
                ).group_by(extract("year", Transaction.transaction_date)).all()

                year_map = {int(r.yr): (Decimal(str(r.income)), Decimal(str(r.expense))) for r in yearly_raw}
                for y in range(start.year, end.year + 1):
                    inc, exp = year_map.get(y, (Decimal("0.00"), Decimal("0.00")))
                    time_series.append(
                        ReportTimeSeriesItem(
                            date_label=str(y),
                            exact_date=f"Year {y}",
                            income=inc,
                            expense=exp,
                            net=inc - exp
                        )
                    )

        # 3. Category distribution (Expenses)
        exp_cat_raw = db.query(
            Category.id.label("cat_id"),
            Category.name.label("cat_name"),
            Category.icon.label("cat_icon"),
            Category.color.label("cat_color"),
            func.count(Transaction.id).label("cnt"),
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("amount")
        ).join(Transaction, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end
        ).group_by(Category.id, Category.name, Category.icon, Category.color).order_by(func.sum(Transaction.amount).desc()).all()

        expense_categories: List[ReportCategoryStatItem] = []
        for r in exp_cat_raw:
            amt = Decimal(str(r.amount))
            pct = float(round((amt / total_exp) * 100, 1)) if total_exp > 0 else 0.0
            expense_categories.append(
                ReportCategoryStatItem(
                    category_id=r.cat_id,
                    category_name=r.cat_name,
                    category_icon=r.cat_icon,
                    category_color=r.cat_color,
                    type="expense",
                    amount=amt,
                    percentage=pct,
                    transaction_count=r.cnt
                )
            )

        # 4. Category distribution (Income)
        inc_cat_raw = db.query(
            Category.id.label("cat_id"),
            Category.name.label("cat_name"),
            Category.icon.label("cat_icon"),
            Category.color.label("cat_color"),
            func.count(Transaction.id).label("cnt"),
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("amount")
        ).join(Transaction, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end
        ).group_by(Category.id, Category.name, Category.icon, Category.color).order_by(func.sum(Transaction.amount).desc()).all()

        income_categories: List[ReportCategoryStatItem] = []
        for r in inc_cat_raw:
            amt = Decimal(str(r.amount))
            pct = float(round((amt / total_inc) * 100, 1)) if total_inc > 0 else 0.0
            income_categories.append(
                ReportCategoryStatItem(
                    category_id=r.cat_id,
                    category_name=r.cat_name,
                    category_icon=r.cat_icon,
                    category_color=r.cat_color,
                    type="income",
                    amount=amt,
                    percentage=pct,
                    transaction_count=r.cnt
                )
            )

        return ComprehensiveReport(
            timeframe=timeframe,
            summary=summary,
            time_series=time_series,
            expense_categories=expense_categories,
            income_categories=income_categories
        )
