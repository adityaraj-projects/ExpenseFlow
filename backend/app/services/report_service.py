import io
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Tuple, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, or_, and_
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.transaction import Transaction, TransactionType
from app.models.category import Category
from app.models.user import User
from app.schemas.report import (
    ReportSummary,
    ReportTimeSeriesItem,
    ReportCategoryStatItem,
    ComprehensiveReport,
    MonthlySourceBreakdownItem,
    MonthOverMonthComparison,
    MonthlyTopCategoryItem,
    MonthlyFinancialSummary
)


def _build_source_filter(source: Optional[str]):
    if not source or source.strip().lower() == "all":
        return None
    s = source.strip().lower()
    if s in ["cash", "manual"]:
        return or_(
            Transaction.source == "cash",
            Transaction.source == "manual",
            Transaction.source.is_(None)
        )
    elif s == "phonepe":
        return Transaction.source == "phonepe"
    return Transaction.source == source.strip()


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
        end_date: Optional[date] = None,
        source: Optional[str] = None
    ) -> ComprehensiveReport:
        start, end = ReportService.resolve_dates(timeframe, start_date, end_date)
        days_span = max(1, (end - start).days + 1)
        source_filter = _build_source_filter(source)

        # 1. Summary aggregations
        sum_query = db.query(
            func.count(Transaction.id).label("tx_count"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end
        )
        if source_filter is not None:
            sum_query = sum_query.filter(source_filter)
        summary_raw = sum_query.first()

        total_inc = Decimal(str(summary_raw.income)) if summary_raw else Decimal("0.00")
        total_exp = Decimal(str(summary_raw.expense)) if summary_raw else Decimal("0.00")
        tx_count = summary_raw.tx_count if summary_raw else 0
        net_savings = total_inc - total_exp
        savings_rate = float(round((net_savings / total_inc) * 100, 1)) if total_inc > 0 else 0.0
        daily_avg = Decimal(str(round(total_exp / Decimal(str(days_span)), 2)))

        # Source breakdown (PhonePe vs Cash)
        breakdown_raw = db.query(
            func.coalesce(func.sum(case((and_(Transaction.type == TransactionType.INCOME, Transaction.source == "phonepe"), Transaction.amount), else_=0)), Decimal("0.00")).label("phonepe_inc"),
            func.coalesce(func.sum(case((and_(Transaction.type == TransactionType.EXPENSE, Transaction.source == "phonepe"), Transaction.amount), else_=0)), Decimal("0.00")).label("phonepe_exp"),
            func.coalesce(func.sum(case((and_(Transaction.type == TransactionType.INCOME, or_(Transaction.source.in_(["cash", "manual"]), Transaction.source.is_(None))), Transaction.amount), else_=0)), Decimal("0.00")).label("cash_inc"),
            func.coalesce(func.sum(case((and_(Transaction.type == TransactionType.EXPENSE, or_(Transaction.source.in_(["cash", "manual"]), Transaction.source.is_(None))), Transaction.amount), else_=0)), Decimal("0.00")).label("cash_exp"),
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end
        ).first()

        phonepe_inc = Decimal(str(breakdown_raw.phonepe_inc)) if breakdown_raw else Decimal("0.00")
        phonepe_exp = Decimal(str(breakdown_raw.phonepe_exp)) if breakdown_raw else Decimal("0.00")
        cash_inc = Decimal(str(breakdown_raw.cash_inc)) if breakdown_raw else Decimal("0.00")
        cash_exp = Decimal(str(breakdown_raw.cash_exp)) if breakdown_raw else Decimal("0.00")

        summary = ReportSummary(
            start_date=start,
            end_date=end,
            total_income=total_inc,
            total_expense=total_exp,
            net_savings=net_savings,
            savings_rate=savings_rate,
            transaction_count=tx_count,
            daily_average_expense=daily_avg,
            phonepe_income=phonepe_inc,
            phonepe_expense=phonepe_exp,
            cash_income=cash_inc,
            cash_expense=cash_exp
        )

        # 2. Time series grouping
        time_series: List[ReportTimeSeriesItem] = []

        if timeframe == "this_week" or (timeframe == "custom" and days_span <= 14):
            # Group daily with weekday (e.g. "Mon 14", "Tue 15")
            daily_q = db.query(
                Transaction.transaction_date.label("dt"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            )
            if source_filter is not None:
                daily_q = daily_q.filter(source_filter)
            daily_raw = daily_q.group_by(Transaction.transaction_date).all()

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
            daily_q = db.query(
                Transaction.transaction_date.label("dt"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            )
            if source_filter is not None:
                daily_q = daily_q.filter(source_filter)
            daily_raw = daily_q.group_by(Transaction.transaction_date).all()

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
            monthly_q = db.query(
                extract("month", Transaction.transaction_date).label("mo"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
            ).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end
            )
            if source_filter is not None:
                monthly_q = monthly_q.filter(source_filter)
            monthly_raw = monthly_q.group_by(extract("month", Transaction.transaction_date)).all()

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
                monthly_q = db.query(
                    extract("year", Transaction.transaction_date).label("yr"),
                    extract("month", Transaction.transaction_date).label("mo"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
                ).filter(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end
                )
                if source_filter is not None:
                    monthly_q = monthly_q.filter(source_filter)
                monthly_raw = monthly_q.group_by(
                    extract("year", Transaction.transaction_date),
                    extract("month", Transaction.transaction_date)
                ).all()

                month_map = {(int(r.yr), int(r.mo)): (Decimal(str(r.income)), Decimal(str(r.expense))) for r in monthly_raw}

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
                yearly_q = db.query(
                    extract("year", Transaction.transaction_date).label("yr"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)), Decimal("0.00")).label("income"),
                    func.coalesce(func.sum(case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)), Decimal("0.00")).label("expense")
                ).filter(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end
                )
                if source_filter is not None:
                    yearly_q = yearly_q.filter(source_filter)
                yearly_raw = yearly_q.group_by(extract("year", Transaction.transaction_date)).all()

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
        exp_cat_q = db.query(
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
        )
        if source_filter is not None:
            exp_cat_q = exp_cat_q.filter(source_filter)
        exp_cat_raw = exp_cat_q.group_by(Category.id, Category.name, Category.icon, Category.color).order_by(func.sum(Transaction.amount).desc()).all()

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
        inc_cat_q = db.query(
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
        )
        if source_filter is not None:
            inc_cat_q = inc_cat_q.filter(source_filter)
        inc_cat_raw = inc_cat_q.group_by(Category.id, Category.name, Category.icon, Category.color).order_by(func.sum(Transaction.amount).desc()).all()

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

    @staticmethod
    def generate_monthly_pdf(
        db: Session,
        user: User,
        month: int,
        year: int
    ) -> bytes:
        """
        Generate a downloadable, high-quality monthly financial statement PDF report.
        Includes user info, monthly period, summary metrics, and a full transaction ledger.
        """
        _, last_day = calendar.monthrange(year, month)
        start_dt = date(year, month, 1)
        end_dt = date(year, month, last_day)

        # Fetch all transactions for this month scoped strictly to user.id
        txs = db.query(Transaction).join(Category).filter(
            Transaction.user_id == user.id,
            Transaction.transaction_date >= start_dt,
            Transaction.transaction_date <= end_dt
        ).order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).all()

        total_income = sum((t.amount for t in txs if t.type == TransactionType.INCOME), Decimal("0.00"))
        total_expense = sum((t.amount for t in txs if t.type == TransactionType.EXPENSE), Decimal("0.00"))
        net_balance = total_income - total_expense
        savings_rate = (net_balance / total_income * 100) if total_income > 0 else Decimal("0.0")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=2
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=12
        )
        section_title = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#1E293B'),
            spaceAfter=8
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#334155')
        )
        table_header = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#0F172A')
        )
        table_cell = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#334155')
        )

        story = []

        # 1. Header
        story.append(Paragraph("<b>ExpenseFlow</b>", title_style))
        story.append(Paragraph("Monthly Financial Statement &bull; Track Today &bull; Save Tomorrow", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=14))

        # 2. User & Statement Details
        month_name = calendar.month_name[month]
        info_data = [
            [
                Paragraph(f"<b>Account Holder:</b> {user.full_name}", body_style),
                Paragraph(f"<b>Statement Period:</b> {month_name} {year}", body_style)
            ],
            [
                Paragraph(f"<b>Email:</b> {user.email}", body_style),
                Paragraph(f"<b>Generated On:</b> {date.today().strftime('%d %B %Y')}", body_style)
            ]
        ]
        info_table = Table(info_data, colWidths=[260, 260])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 14))

        # 3. Monthly Summary Cards
        summary_data = [
            [
                Paragraph(f"<b>Total Income</b><br/><font size=12 color='#10B981'><b>₹{total_income:,.2f}</b></font>", body_style),
                Paragraph(f"<b>Total Expenses</b><br/><font size=12 color='#EF4444'><b>₹{total_expense:,.2f}</b></font>", body_style),
                Paragraph(f"<b>Net Savings</b><br/><font size=12 color='#2563EB'><b>₹{net_balance:,.2f}</b></font>", body_style),
                Paragraph(f"<b>Savings Rate</b><br/><font size=12 color='#0F172A'><b>{savings_rate:.1f}%</b></font>", body_style)
            ]
        ]
        sum_table = Table(summary_data, colWidths=[130, 130, 130, 130])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 9),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 14))

        # 4. Source Breakdown & Category Breakdown
        phonepe_inc = sum((t.amount for t in txs if t.source == "phonepe" and t.type == TransactionType.INCOME), Decimal("0.00"))
        phonepe_exp = sum((t.amount for t in txs if t.source == "phonepe" and t.type == TransactionType.EXPENSE), Decimal("0.00"))
        cash_inc = sum((t.amount for t in txs if (t.source in ["cash", "manual", None, ""]) and t.type == TransactionType.INCOME), Decimal("0.00"))
        cash_exp = sum((t.amount for t in txs if (t.source in ["cash", "manual", None, ""]) and t.type == TransactionType.EXPENSE), Decimal("0.00"))

        src_rows = [
            [
                Paragraph("<b>Payment Source</b>", table_header),
                Paragraph("<b>Income (₹)</b>", table_header),
                Paragraph("<b>Expense (₹)</b>", table_header),
                Paragraph("<b>Net (₹)</b>", table_header)
            ],
            [
                Paragraph("PhonePe", table_cell),
                Paragraph(f"₹{phonepe_inc:,.2f}", table_cell),
                Paragraph(f"₹{phonepe_exp:,.2f}", table_cell),
                Paragraph(f"₹{(phonepe_inc - phonepe_exp):,.2f}", table_cell)
            ],
            [
                Paragraph("Cash / Manual", table_cell),
                Paragraph(f"₹{cash_inc:,.2f}", table_cell),
                Paragraph(f"₹{cash_exp:,.2f}", table_cell),
                Paragraph(f"₹{(cash_inc - cash_exp):,.2f}", table_cell)
            ]
        ]
        src_table = Table(src_rows, colWidths=[130, 130, 130, 130])
        src_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(Paragraph("<b>Source Breakdown</b>", section_title))
        story.append(src_table)
        story.append(Spacer(1, 14))

        # Top Spending Categories Breakdown
        cat_map = {}
        for t in txs:
            if t.type == TransactionType.EXPENSE:
                cname = t.category.name if t.category else "Uncategorized"
                cat_map[cname] = cat_map.get(cname, Decimal("0.00")) + t.amount

        if cat_map:
            sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:6]
            cat_rows = [
                [
                    Paragraph("<b>Top Expense Categories</b>", table_header),
                    Paragraph("<b>Amount (₹)</b>", table_header),
                    Paragraph("<b>% of Spending</b>", table_header)
                ]
            ]
            for cname, camt in sorted_cats:
                cpct = (camt / total_expense * 100) if total_expense > 0 else Decimal("0.0")
                cat_rows.append([
                    Paragraph(cname, table_cell),
                    Paragraph(f"₹{camt:,.2f}", table_cell),
                    Paragraph(f"{cpct:.1f}%", table_cell)
                ])
            cat_table = Table(cat_rows, colWidths=[200, 160, 160])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(Paragraph("<b>Category Breakdown</b>", section_title))
            story.append(cat_table)
            story.append(Spacer(1, 16))

        # 5. Transaction History Table
        story.append(Paragraph(f"Transaction History ({len(txs)} transactions)", section_title))
        tx_rows = [
            [
                Paragraph("<b>Date / Time</b>", table_header),
                Paragraph("<b>Description</b>", table_header),
                Paragraph("<b>Category</b>", table_header),
                Paragraph("<b>Source</b>", table_header),
                Paragraph("<b>Income (₹)</b>", table_header),
                Paragraph("<b>Expense (₹)</b>", table_header)
            ]
        ]

        for t in txs:
            dt_str = t.transaction_date.strftime("%d %b %Y")
            if t.transaction_time:
                dt_str += f"<br/><font color='#64748B' size=7>{t.transaction_time}</font>"

            src_label = "PhonePe" if t.source == "phonepe" else "Cash / Manual"
            inc_val = f"₹{t.amount:,.2f}" if t.type == TransactionType.INCOME else "—"
            exp_val = f"₹{t.amount:,.2f}" if t.type == TransactionType.EXPENSE else "—"

            tx_rows.append([
                Paragraph(dt_str, table_cell),
                Paragraph(t.description, table_cell),
                Paragraph(t.category.name if t.category else "Uncategorized", table_cell),
                Paragraph(src_label, table_cell),
                Paragraph(inc_val, table_cell),
                Paragraph(exp_val, table_cell)
            ])

        # Closing totals row
        tx_rows.append([
            Paragraph("<b>Closing Totals</b>", table_header),
            Paragraph(f"<b>{len(txs)} Records</b>", table_header),
            Paragraph("—", table_header),
            Paragraph("—", table_header),
            Paragraph(f"<b>₹{total_income:,.2f}</b>", table_header),
            Paragraph(f"<b>₹{total_expense:,.2f}</b>", table_header)
        ])

        table = Table(tx_rows, colWidths=[80, 160, 95, 75, 55, 55], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(table)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    @staticmethod
    def get_monthly_summary(
        db: Session,
        user_id: int,
        month: int,
        year: int
    ) -> MonthlyFinancialSummary:
        """
        Calculates smart monthly financial summary KPIs, source breakdowns,
        top categories, month-over-month comparisons, and rule-based insights.
        """
        import calendar
        month_name = calendar.month_name[month]
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # 1. Monthly Total Income & Expense
        inc_res = db.query(
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            func.count(Transaction.id)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).first()
        total_income = Decimal(str(inc_res[0] or "0.00"))
        income_count = int(inc_res[1] or 0)

        exp_res = db.query(
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            func.count(Transaction.id)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).first()
        total_expense = Decimal(str(exp_res[0] or "0.00"))
        expense_count = int(exp_res[1] or 0)

        total_transactions = income_count + expense_count
        net_savings = total_income - total_expense
        savings_rate = round(float((net_savings / total_income) * 100), 1) if total_income > 0 else 0.0

        # 2. Source Breakdown (PhonePe vs Cash/Manual vs Other)
        sources_data = db.query(
            Transaction.source,
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            func.count(Transaction.id)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).group_by(Transaction.source, Transaction.type).all()

        source_map = {
            "phonepe": {"income": Decimal("0.00"), "expense": Decimal("0.00"), "inc_cnt": 0, "exp_cnt": 0},
            "cash": {"income": Decimal("0.00"), "expense": Decimal("0.00"), "inc_cnt": 0, "exp_cnt": 0},
            "other": {"income": Decimal("0.00"), "expense": Decimal("0.00"), "inc_cnt": 0, "exp_cnt": 0},
        }
        for src, tx_type, amt, cnt in sources_data:
            s_key = (src or "").strip().lower()
            target_key = "phonepe" if s_key == "phonepe" else ("cash" if s_key in ["cash", "manual", ""] else "other")
            if tx_type == TransactionType.INCOME:
                source_map[target_key]["income"] += Decimal(str(amt or "0.00"))
                source_map[target_key]["inc_cnt"] += int(cnt or 0)
            else:
                source_map[target_key]["expense"] += Decimal(str(amt or "0.00"))
                source_map[target_key]["exp_cnt"] += int(cnt or 0)

        source_breakdown = [
            MonthlySourceBreakdownItem(
                source="phonepe",
                label="PhonePe",
                income=source_map["phonepe"]["income"],
                expense=source_map["phonepe"]["expense"],
                net=source_map["phonepe"]["income"] - source_map["phonepe"]["expense"],
                income_count=source_map["phonepe"]["inc_cnt"],
                expense_count=source_map["phonepe"]["exp_cnt"],
                total_count=source_map["phonepe"]["inc_cnt"] + source_map["phonepe"]["exp_cnt"]
            ),
            MonthlySourceBreakdownItem(
                source="cash",
                label="Cash / Manual",
                income=source_map["cash"]["income"],
                expense=source_map["cash"]["expense"],
                net=source_map["cash"]["income"] - source_map["cash"]["expense"],
                income_count=source_map["cash"]["inc_cnt"],
                expense_count=source_map["cash"]["exp_cnt"],
                total_count=source_map["cash"]["inc_cnt"] + source_map["cash"]["exp_cnt"]
            )
        ]
        if source_map["other"]["income"] > 0 or source_map["other"]["expense"] > 0:
            source_breakdown.append(MonthlySourceBreakdownItem(
                source="other",
                label="Other Sources",
                income=source_map["other"]["income"],
                expense=source_map["other"]["expense"],
                net=source_map["other"]["income"] - source_map["other"]["expense"],
                income_count=source_map["other"]["inc_cnt"],
                expense_count=source_map["other"]["exp_cnt"],
                total_count=source_map["other"]["inc_cnt"] + source_map["other"]["exp_cnt"]
            ))

        # 3. Top Spending Categories
        cat_stats = db.query(
            Category.id,
            Category.name,
            Category.icon,
            Category.color,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("cat_total"),
            func.count(Transaction.id).label("cat_count")
        ).outerjoin(Category, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).group_by(Category.id, Category.name, Category.icon, Category.color).order_by(
            func.sum(Transaction.amount).desc()
        ).limit(10).all()

        top_categories = []
        for cid, cname, cicon, ccolor, ctotal, ccount in cat_stats:
            amt = Decimal(str(ctotal or "0.00"))
            pct = round(float((amt / total_expense) * 100), 1) if total_expense > 0 else 0.0
            top_categories.append(MonthlyTopCategoryItem(
                category_id=cid,
                category_name=cname or "Uncategorized",
                category_icon=cicon or "tag",
                category_color=ccolor or "#64748B",
                amount=amt,
                percentage=pct,
                transaction_count=int(ccount or 0)
            ))

        # 4. Month-over-Month Comparison
        prev_month = 12 if month == 1 else month - 1
        prev_year = year - 1 if month == 1 else year
        prev_month_name = calendar.month_name[prev_month]
        _, prev_last_day = calendar.monthrange(prev_year, prev_month)
        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, prev_last_day)

        prev_inc = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end
        ).scalar()
        prev_income = Decimal(str(prev_inc or "0.00"))

        prev_exp = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end
        ).scalar()
        prev_expense = Decimal(str(prev_exp or "0.00"))

        prev_net = prev_income - prev_expense
        prev_rate = round(float((prev_net / prev_income) * 100), 1) if prev_income > 0 else 0.0

        # Expense change
        expense_change_pct = None
        if prev_expense > 0:
            expense_change_pct = round(float(((total_expense - prev_expense) / prev_expense) * 100), 1)
            if total_expense < prev_expense:
                expense_dir = "decreased"
            elif total_expense > prev_expense:
                expense_dir = "increased"
            else:
                expense_dir = "unchanged"
        else:
            expense_dir = "no_baseline" if total_expense > 0 else "unchanged"

        # Income change
        income_change_pct = None
        if prev_income > 0:
            income_change_pct = round(float(((total_income - prev_income) / prev_income) * 100), 1)
            if total_income > prev_income:
                income_dir = "increased"
            elif total_income < prev_income:
                income_dir = "decreased"
            else:
                income_dir = "unchanged"
        else:
            income_dir = "no_baseline" if total_income > 0 else "unchanged"

        # Savings change
        savings_change_pct = None
        if prev_net != 0:
            savings_change_pct = round(float(((net_savings - prev_net) / abs(prev_net)) * 100), 1)
            if net_savings > prev_net:
                savings_dir = "improved"
            elif net_savings < prev_net:
                savings_dir = "decreased"
            else:
                savings_dir = "unchanged"
        else:
            savings_dir = "improved" if net_savings > 0 else ("decreased" if net_savings < 0 else "unchanged")

        # Summary message
        if expense_dir == "decreased" and expense_change_pct is not None:
            summary_message = f"Your expenses decreased by {abs(expense_change_pct):.1f}% compared with last month."
        elif expense_dir == "increased" and expense_change_pct is not None:
            summary_message = f"Your expenses increased by {abs(expense_change_pct):.1f}% compared with last month."
        elif expense_dir == "unchanged":
            summary_message = "Your expenses remained steady compared with last month."
        else:
            summary_message = f"Recorded ₹{total_expense:,.2f} in expenses (no prior baseline for {prev_month_name})."

        comparison = MonthOverMonthComparison(
            prev_month=prev_month,
            prev_year=prev_year,
            prev_month_name=prev_month_name,
            prev_income=prev_income,
            prev_expense=prev_expense,
            prev_net_savings=prev_net,
            prev_savings_rate=prev_rate,
            income_change_pct=income_change_pct,
            expense_change_pct=expense_change_pct,
            savings_change_pct=savings_change_pct,
            expense_change_direction=expense_dir,
            income_change_direction=income_dir,
            savings_change_direction=savings_dir,
            summary_message=summary_message
        )

        # 5. Financial Rule-Based Insights
        insights = []
        if expense_dir == "decreased" and expense_change_pct is not None:
            insights.append(f"You spent {abs(expense_change_pct):.1f}% less than last month.")
        elif expense_dir == "increased" and expense_change_pct is not None:
            insights.append(f"Expenses rose by {abs(expense_change_pct):.1f}% compared with {prev_month_name}.")

        if top_categories:
            top_c = top_categories[0]
            insights.append(f"{top_c.category_name} is your highest spending category this month (₹{top_c.amount:,.2f}, {top_c.percentage:.0f}% of total spending).")

        if total_income > 0:
            if prev_income > 0 and prev_rate is not None and prev_rate != savings_rate:
                insights.append(f"Your savings rate shifted from {prev_rate:.0f}% last month to {savings_rate:.0f}%.")
            else:
                insights.append(f"Your savings rate reached {savings_rate:.1f}% with ₹{net_savings:,.2f} saved.")

        phonepe_exp = source_map["phonepe"]["expense"]
        cash_exp = source_map["cash"]["expense"]
        if phonepe_exp > cash_exp and phonepe_exp > 0:
            insights.append(f"Most of your transactions were made through PhonePe (₹{phonepe_exp:,.2f} spent).")
        elif cash_exp > phonepe_exp and cash_exp > 0:
            insights.append(f"Cash spending was your primary channel this month (₹{cash_exp:,.2f} spent).")
        elif cash_exp > 0 and phonepe_exp > 0:
            insights.append("Spending was evenly distributed between PhonePe and Cash payments.")

        # Check cash spending trend
        prev_cash_exp = db.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            or_(Transaction.source == "cash", Transaction.source == "manual", Transaction.source.is_(None)),
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end
        ).scalar()
        prev_cash_expense = Decimal(str(prev_cash_exp or "0.00"))
        if prev_cash_expense > 0 and cash_exp > prev_cash_expense:
            insights.append("Cash spending increased compared with last month.")
        elif prev_cash_expense > 0 and cash_exp < prev_cash_expense:
            insights.append("Cash spending decreased compared with last month.")

        if not insights:
            insights.append("No financial transactions recorded for this month yet.")

        return MonthlyFinancialSummary(
            month=month,
            year=year,
            month_name=month_name,
            total_income=total_income,
            total_expense=total_expense,
            net_savings=net_savings,
            savings_rate=savings_rate,
            income_count=income_count,
            expense_count=expense_count,
            total_transactions=total_transactions,
            source_breakdown=source_breakdown,
            top_categories=top_categories,
            comparison=comparison,
            insights=insights
        )
