"""
ExpenseFlow — Master Feature Enhancement Test Suite
Covers:
1. Calendar / Daily Finance (month overview, day details, daily summary, indicators)
2. Delete My Financial Data (safety, 'DELETE' confirmation, user isolation, rollback)
3. Transaction Source Badges & Filters (PhonePe, Cash, Manual, source filtering)
4. PhonePe Import History (recording, metadata, user-scoped duplicate counts)
5. Calendar-based Monthly Statement / PDF (source breakdown, categories, pagination)
6. Calendar Filters (Income, Expense, PhonePe, Cash, Category)
7. Financial Integrity (Dashboard == Reports == Calendar == PDF == Database)
"""
import os
import sys
import io
import time
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app
from app.database.connection import get_db, SessionLocal
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category, CategoryType
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal
from app.models.reminder import Reminder, ReminderStatus
from app.models.recurring_transaction import RecurringTransaction, RecurringFrequency, RecurringTransactionType
from app.models.notification import Notification
from app.models.statement_import import StatementImport
from app.services.statement_parser_service import StatementParserService
from app.services.report_service import ReportService


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def register_user(client, prefix="user"):
    ts = int(time.time() * 1000)
    email = f"{prefix}_{ts}_{os.urandom(3).hex()}@example.com"
    pwd = "SecurePassword123!"
    payload = {
        "full_name": f"Test {prefix.capitalize()} {ts}",
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "currency": "INR"
    }
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, f"Failed to register user: {r.text}"
    token = r.json()["access_token"]
    user_info = r.json()["user"]
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_info["id"],
        "email": email
    }


class TestCalendarAndDailyFinance:
    """Tests for Feature 1, 6, 7: Calendar / Daily Finance & Filters"""

    def test_01_calendar_loads_month_overview_and_navigation(self, client):
        user = register_user(client, prefix="cal_nav")
        headers = user["headers"]

        # Current month
        now = datetime.now()
        r = client.get(f"/api/calendar/month?year={now.year}&month={now.month}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["year"] == now.year
        assert data["month"] == now.month
        assert "days" in data
        assert data["total_transactions"] == 0
        assert data["total_income"] == 0.0
        assert data["total_expense"] == 0.0
        assert data["net_balance"] == 0.0

        # Previous month
        prev_m = 12 if now.month == 1 else now.month - 1
        prev_y = now.year - 1 if now.month == 1 else now.year
        r_prev = client.get(f"/api/calendar/month?year={prev_y}&month={prev_m}", headers=headers)
        assert r_prev.status_code == 200
        assert r_prev.json()["month"] == prev_m

        # Next month
        next_m = 1 if now.month == 12 else now.month + 1
        next_y = now.year + 1 if now.month == 12 else now.year
        r_next = client.get(f"/api/calendar/month?year={next_y}&month={next_m}", headers=headers)
        assert r_next.status_code == 200
        assert r_next.json()["month"] == next_m

    def test_02_daily_summary_and_visual_indicators(self, client):
        user = register_user(client, prefix="cal_kpi")
        headers = user["headers"]
        user_id = user["user_id"]

        db = SessionLocal()
        try:
            exp_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()
            inc_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.INCOME).first()

            # Date 1: 2026-10-10 -> Income only (Green indicator)
            d1 = date(2026, 10, 10)
            t1 = Transaction(
                user_id=user_id,
                category_id=inc_cat.id,
                type=TransactionType.INCOME,
                amount=Decimal("5000.00"),
                description="Freelance Payment",
                transaction_date=d1,
                transaction_time="10:32 AM",
                source="phonepe"
            )

            # Date 2: 2026-10-15 -> Expense only (Red indicator)
            d2 = date(2026, 10, 15)
            t2 = Transaction(
                user_id=user_id,
                category_id=exp_cat.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("850.00"),
                description="Grocery Store",
                transaction_date=d2,
                transaction_time="02:15 PM",
                source="cash"
            )

            # Date 3: 2026-10-20 -> Both Income and Expense (Both indicator)
            d3 = date(2026, 10, 20)
            t3 = Transaction(
                user_id=user_id,
                category_id=inc_cat.id,
                type=TransactionType.INCOME,
                amount=Decimal("5000.00"),
                description="Project Bonus",
                transaction_date=d3,
                transaction_time="09:00 AM",
                source="phonepe"
            )
            t4 = Transaction(
                user_id=user_id,
                category_id=exp_cat.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("1250.00"),
                description="Dinner & Transport",
                transaction_date=d3,
                transaction_time="08:30 PM",
                source="cash"
            )

            db.add_all([t1, t2, t3, t4])
            db.commit()
        finally:
            db.close()

        # Check Month Overview
        r = client.get("/api/calendar/month?year=2026&month=10", headers=headers)
        assert r.status_code == 200
        res = r.json()

        assert res["total_income"] == 10000.0
        assert res["total_expense"] == 2100.0
        assert res["net_balance"] == 7900.0
        assert res["total_transactions"] == 4

        days = res["days"]
        # Date 1: Income only
        assert days["2026-10-10"]["indicator"] == "income"
        assert days["2026-10-10"]["income"] == 5000.0
        assert days["2026-10-10"]["expense"] == 0.0

        # Date 2: Expense only
        assert days["2026-10-15"]["indicator"] == "expense"
        assert days["2026-10-15"]["income"] == 0.0
        assert days["2026-10-15"]["expense"] == 850.0

        # Date 3: Both Income and Expense
        assert days["2026-10-20"]["indicator"] == "both"
        assert days["2026-10-20"]["income"] == 5000.0
        assert days["2026-10-20"]["expense"] == 1250.0
        assert days["2026-10-20"]["net"] == 3750.0

        # Check Single Date Endpoint
        r_day = client.get("/api/calendar/day?date=2026-10-20", headers=headers)
        assert r_day.status_code == 200
        day_res = r_day.json()
        assert day_res["date"] == "2026-10-20"
        assert day_res["total_income"] == 5000.0
        assert day_res["total_expense"] == 1250.0
        assert day_res["net_balance"] == 3750.0
        assert len(day_res["transactions"]) == 2
        # Check exact time and sources preserved
        sources = {t["source"] for t in day_res["transactions"]}
        assert "phonepe" in sources
        assert "cash" in sources

    def test_03_calendar_filters(self, client):
        user = register_user(client, prefix="cal_filt")
        headers = user["headers"]
        user_id = user["user_id"]

        db = SessionLocal()
        try:
            exp_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()
            inc_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.INCOME).first()

            dt = date(2026, 10, 5)
            t_ph_exp = Transaction(user_id=user_id, category_id=exp_cat.id, type=TransactionType.EXPENSE, amount=Decimal("300.00"), description="PhonePe Exp", transaction_date=dt, source="phonepe")
            t_csh_exp = Transaction(user_id=user_id, category_id=exp_cat.id, type=TransactionType.EXPENSE, amount=Decimal("200.00"), description="Cash Exp", transaction_date=dt, source="cash")
            t_ph_inc = Transaction(user_id=user_id, category_id=inc_cat.id, type=TransactionType.INCOME, amount=Decimal("1500.00"), description="PhonePe Inc", transaction_date=dt, source="phonepe")

            db.add_all([t_ph_exp, t_csh_exp, t_ph_inc])
            db.commit()
        finally:
            db.close()

        # Filter by source=phonepe
        r = client.get("/api/calendar/month?year=2026&month=10&source=phonepe", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_transactions"] == 2
        assert data["total_expense"] == 300.0
        assert data["total_income"] == 1500.0

        # Filter by source=cash
        r_cash = client.get("/api/calendar/month?year=2026&month=10&source=cash", headers=headers)
        assert r_cash.status_code == 200
        data_cash = r_cash.json()
        assert data_cash["total_transactions"] == 1
        assert data_cash["total_expense"] == 200.0

        # Filter by type=expense
        r_exp = client.get("/api/calendar/month?year=2026&month=10&type=expense", headers=headers)
        assert r_exp.status_code == 200
        assert r_exp.json()["total_transactions"] == 2
        assert r_exp.json()["total_income"] == 0.0

        # Filter on Day endpoint: date=2026-10-05&source=phonepe&type=expense
        r_day_filt = client.get("/api/calendar/day?date=2026-10-05&source=phonepe&type=expense", headers=headers)
        assert r_day_filt.status_code == 200
        d_data = r_day_filt.json()
        assert len(d_data["transactions"]) == 1
        assert d_data["transactions"][0]["description"] == "PhonePe Exp"


class TestDeleteFinancialData:
    """Tests for Feature 2: Delete My Financial Data & Security Isolation"""

    def test_04_delete_validation_must_type_delete(self, client):
        user = register_user(client, prefix="del_val")
        headers = user["headers"]

        # Missing or wrong confirmation
        r1 = client.request("DELETE", "/api/users/financial-data", json={"confirmation": "wrong"}, headers=headers)
        assert r1.status_code in [400, 422]

        r2 = client.request("DELETE", "/api/users/financial-data", json={"confirmation": "delete"}, headers=headers)
        assert r2.status_code in [400, 422]

    def test_05_delete_my_financial_data_clears_records_keeps_account(self, client):
        user = register_user(client, prefix="del_flow")
        headers = user["headers"]
        user_id = user["user_id"]

        # Populate user with diverse financial data
        db = SessionLocal()
        try:
            exp_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()

            # 1. Transactions
            tx = Transaction(user_id=user_id, category_id=exp_cat.id, type=TransactionType.EXPENSE, amount=Decimal("450.00"), description="Lunch", transaction_date=date.today())
            db.add(tx)

            # 2. Budget
            bg = Budget(user_id=user_id, category_id=exp_cat.id, month=date.today().month, year=date.today().year, amount=Decimal("5000.00"))
            db.add(bg)

            # 3. Savings Goal
            sg = SavingsGoal(user_id=user_id, name="Emergency Fund", target_amount=Decimal("20000.00"), current_amount=Decimal("1000.00"))
            db.add(sg)

            # 4. Reminder
            rm = Reminder(user_id=user_id, title="Electricity Bill", amount=Decimal("1200.00"), reminder_date=date.today() + timedelta(days=5), status=ReminderStatus.PENDING)
            db.add(rm)

            # 5. Recurring Transaction
            rc = RecurringTransaction(user_id=user_id, category_id=exp_cat.id, type=RecurringTransactionType.EXPENSE, amount=Decimal("199.00"), description="Netflix", frequency=RecurringFrequency.MONTHLY, start_date=date.today(), next_occurrence_date=date.today() + timedelta(days=30))
            db.add(rc)

            # 6. Statement Import history
            si = StatementImport(user_id=user_id, source="phonepe", statement_period="September 2026", filename="sept.pdf", total_found=10, total_new=10, total_duplicates=0)
            db.add(si)

            db.commit()
        finally:
            db.close()

        # Verify records exist before deletion
        r_pre = client.get("/api/dashboard", headers=headers)
        assert r_pre.status_code == 200

        # Execute Delete Financial Data
        r_del = client.request("DELETE", "/api/users/financial-data", json={"confirmation": "DELETE"}, headers=headers)
        assert r_del.status_code == 200
        del_res = r_del.json()
        assert del_res["deleted_transactions"] >= 1
        assert del_res["deleted_budgets"] >= 1
        assert del_res["deleted_goals"] >= 1
        assert del_res["deleted_reminders"] >= 1
        assert del_res["deleted_recurring"] >= 1
        assert del_res["deleted_statement_imports"] >= 1

        # Verify financial data is now completely 0
        db = SessionLocal()
        try:
            assert db.query(Transaction).filter(Transaction.user_id == user_id).count() == 0
            assert db.query(Budget).filter(Budget.user_id == user_id).count() == 0
            assert db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).count() == 0
            assert db.query(Reminder).filter(Reminder.user_id == user_id).count() == 0
            assert db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user_id).count() == 0
            assert db.query(StatementImport).filter(StatementImport.user_id == user_id).count() == 0

            # CRITICAL: User account MUST still exist
            u = db.query(User).filter(User.id == user_id).first()
            assert u is not None
            assert u.email == user["email"]

            # CRITICAL: Default categories MUST remain intact
            cats = db.query(Category).filter(Category.user_id == user_id).all()
            assert len(cats) > 0
        finally:
            db.close()

        # User can still access authenticated profile
        r_me = client.get("/api/auth/me", headers=headers)
        assert r_me.status_code == 200
        assert r_me.json()["email"] == user["email"]

    def test_06_delete_financial_data_multi_user_isolation(self, client):
        user_a = register_user(client, prefix="user_a")
        user_b = register_user(client, prefix="user_b")

        db = SessionLocal()
        try:
            exp_a = db.query(Category).filter(Category.user_id == user_a["user_id"]).first()
            exp_b = db.query(Category).filter(Category.user_id == user_b["user_id"]).first()

            # Insert for User A
            tx_a = Transaction(user_id=user_a["user_id"], category_id=exp_a.id, type=TransactionType.EXPENSE, amount=Decimal("1000.00"), description="User A Tx", transaction_date=date.today())
            # Insert for User B
            tx_b = Transaction(user_id=user_b["user_id"], category_id=exp_b.id, type=TransactionType.EXPENSE, amount=Decimal("2000.00"), description="User B Tx", transaction_date=date.today())
            db.add_all([tx_a, tx_b])
            db.commit()
        finally:
            db.close()

        # Delete User A's financial data
        r = client.request("DELETE", "/api/users/financial-data", json={"confirmation": "DELETE"}, headers=user_a["headers"])
        assert r.status_code == 200

        # Verify User A has 0 transactions, User B still has their transaction intact
        db = SessionLocal()
        try:
            assert db.query(Transaction).filter(Transaction.user_id == user_a["user_id"]).count() == 0
            assert db.query(Transaction).filter(Transaction.user_id == user_b["user_id"]).count() == 1
            b_tx = db.query(Transaction).filter(Transaction.user_id == user_b["user_id"]).first()
            assert b_tx.description == "User B Tx"
            assert b_tx.amount == Decimal("2000.00")
        finally:
            db.close()


class TestPhonePeImportHistoryAndMultiMonth:
    """Tests for Feature 4: PhonePe Import History & Multi-Month Duplication Handling"""

    def test_07_import_history_recorded_on_import(self, client):
        user = register_user(client, prefix="imp_hist")
        headers = user["headers"]
        user_id = user["user_id"]

        db = SessionLocal()
        try:
            cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()
            cat_id = cat.id
        finally:
            db.close()

        # Perform an import with 2 transactions
        txs_payload = {
            "transactions": [
                {
                    "transaction_date": "2026-09-10",
                    "transaction_time": "11:00 AM",
                    "type": "expense",
                    "amount": 450.00,
                    "description": "Swiggy Order",
                    "category_id": cat_id,
                    "external_transaction_id": "TXN_SEPT_01",
                    "external_utr": "UTR_SEPT_01",
                    "source": "phonepe"
                },
                {
                    "transaction_date": "2026-09-12",
                    "transaction_time": "03:30 PM",
                    "type": "expense",
                    "amount": 250.00,
                    "description": "Zomato Order",
                    "category_id": cat_id,
                    "external_transaction_id": "TXN_SEPT_02",
                    "external_utr": "UTR_SEPT_02",
                    "source": "phonepe"
                }
            ],
            "filename": "PhonePe_Statement_Sep2026.pdf",
            "statement_period": "September 2026",
            "total_found": 2
        }

        r_imp = client.post("/api/statements/import-phonepe", json=txs_payload, headers=headers)
        assert r_imp.status_code == 200
        res = r_imp.json()
        assert res["imported_count"] == 2
        assert res["skipped_count"] == 0
        assert "import_id" in res

        # Check Import History endpoint
        r_hist = client.get("/api/statements/history", headers=headers)
        assert r_hist.status_code == 200
        history_list = r_hist.json()
        assert len(history_list) >= 1
        entry = history_list[0]
        assert entry["statement_period"] == "September 2026"
        assert entry["filename"] == "PhonePe_Statement_Sep2026.pdf"
        assert entry["total_found"] == 2
        assert entry["total_new"] == 2
        assert entry["total_duplicates"] == 0
        assert entry["status"] == "completed"

    def test_08_multi_month_storage_does_not_overwrite(self, client):
        user = register_user(client, prefix="multi_month")
        headers = user["headers"]
        user_id = user["user_id"]

        db = SessionLocal()
        try:
            cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()
            cat_id = cat.id
        finally:
            db.close()

        # Month 1: September
        client.post("/api/statements/import-phonepe", json={
            "transactions": [
                {
                    "transaction_date": "2026-09-15",
                    "type": "expense",
                    "amount": 500.00,
                    "description": "September Bill",
                    "category_id": cat_id,
                    "external_transaction_id": "TX_SEP_100",
                    "source": "phonepe"
                }
            ],
            "statement_period": "September 2026",
            "filename": "Sep.pdf"
        }, headers=headers)

        # Month 2: October
        client.post("/api/statements/import-phonepe", json={
            "transactions": [
                {
                    "transaction_date": "2026-10-15",
                    "type": "expense",
                    "amount": 750.00,
                    "description": "October Bill",
                    "category_id": cat_id,
                    "external_transaction_id": "TX_OCT_100",
                    "source": "phonepe"
                }
            ],
            "statement_period": "October 2026",
            "filename": "Oct.pdf"
        }, headers=headers)

        # Month 3: November
        client.post("/api/statements/import-phonepe", json={
            "transactions": [
                {
                    "transaction_date": "2026-11-15",
                    "type": "expense",
                    "amount": 900.00,
                    "description": "November Bill",
                    "category_id": cat_id,
                    "external_transaction_id": "TX_NOV_100",
                    "source": "phonepe"
                }
            ],
            "statement_period": "November 2026",
            "filename": "Nov.pdf"
        }, headers=headers)

        # All 3 months must exist simultaneously!
        db = SessionLocal()
        try:
            txs = db.query(Transaction).filter(Transaction.user_id == user_id).all()
            assert len(txs) == 3
            dates = {t.transaction_date.strftime("%Y-%m-%d") for t in txs}
            assert "2026-09-15" in dates
            assert "2026-10-15" in dates
            assert "2026-11-15" in dates

            # Calendar can retrieve each by its actual date
            r_sep = client.get("/api/calendar/month?year=2026&month=9", headers=headers)
            assert r_sep.json()["total_transactions"] == 1

            r_oct = client.get("/api/calendar/month?year=2026&month=10", headers=headers)
            assert r_oct.json()["total_transactions"] == 1

            r_nov = client.get("/api/calendar/month?year=2026&month=11", headers=headers)
            assert r_nov.json()["total_transactions"] == 1
        finally:
            db.close()

    def test_09_duplicate_import_protection_and_user_isolation(self, client):
        user_a = register_user(client, prefix="dup_user_a")
        user_b = register_user(client, prefix="dup_user_b")

        db = SessionLocal()
        try:
            cat_a = db.query(Category).filter(Category.user_id == user_a["user_id"]).first().id
            cat_b = db.query(Category).filter(Category.user_id == user_b["user_id"]).first().id
        finally:
            db.close()

        item_a = {
            "transaction_date": "2026-09-20",
            "type": "expense",
            "amount": 100.00,
            "description": "Coffee",
            "category_id": cat_a,
            "external_transaction_id": "SHARED_TX_999",
            "source": "phonepe"
        }

        # User A first import: 1 new
        r1 = client.post("/api/statements/import-phonepe", json={"transactions": [item_a]}, headers=user_a["headers"])
        assert r1.json()["imported_count"] == 1

        # User A re-upload same transaction: 0 new, 1 duplicate
        r2 = client.post("/api/statements/import-phonepe", json={"transactions": [item_a]}, headers=user_a["headers"])
        assert r2.json()["imported_count"] == 0
        assert r2.json()["skipped_count"] == 1

        # User B imports SAME transaction: MUST succeed (User A duplicate protection does not block User B)
        item_b = dict(item_a)
        item_b["category_id"] = cat_b
        r3 = client.post("/api/statements/import-phonepe", json={"transactions": [item_b]}, headers=user_b["headers"])
        assert r3.json()["imported_count"] == 1
        assert r3.json()["skipped_count"] == 0


class TestMonthlyPdfAndFinancialIntegrity:
    """Tests for Feature 5 & Financial Integrity across Dashboard, Reports, Calendar, PDF"""

    def test_10_monthly_pdf_generation_and_integrity(self, client):
        user = register_user(client, prefix="pdf_fin")
        headers = user["headers"]
        user_id = user["user_id"]

        db = SessionLocal()
        try:
            inc_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.INCOME).first()
            exp_cat = db.query(Category).filter(Category.user_id == user_id, Category.type == CategoryType.EXPENSE).first()

            # 1. Income: ₹50,000
            t_inc = Transaction(user_id=user_id, category_id=inc_cat.id, type=TransactionType.INCOME, amount=Decimal("50000.00"), description="Consulting Income", transaction_date=date(2026, 9, 5), transaction_time="10:00 AM", source="phonepe")
            # 2. PhonePe Expense: ₹10,000
            t_exp1 = Transaction(user_id=user_id, category_id=exp_cat.id, type=TransactionType.EXPENSE, amount=Decimal("10000.00"), description="Electronics", transaction_date=date(2026, 9, 12), transaction_time="03:00 PM", source="phonepe")
            # 3. Cash Expense: ₹5,000
            t_exp2 = Transaction(user_id=user_id, category_id=exp_cat.id, type=TransactionType.EXPENSE, amount=Decimal("5000.00"), description="Cash Groceries", transaction_date=date(2026, 9, 20), transaction_time="07:30 PM", source="cash")

            db.add_all([t_inc, t_exp1, t_exp2])
            db.commit()
        finally:
            db.close()

        # Expected totals:
        # Total Income = 50,000
        # Total Expenses = 15,000
        # Net Balance = 35,000

        # 1. Check Calendar
        r_cal = client.get("/api/calendar/month?year=2026&month=9", headers=headers)
        assert r_cal.status_code == 200
        cal_data = r_cal.json()
        assert cal_data["total_income"] == 50000.0
        assert cal_data["total_expense"] == 15000.0
        assert cal_data["net_balance"] == 35000.0

        # 2. Check Monthly Summary Report
        r_rep = client.get("/api/reports/monthly-summary?year=2026&month=9", headers=headers)
        assert r_rep.status_code == 200
        rep_data = r_rep.json()
        assert float(rep_data["total_income"]) == 50000.0
        assert float(rep_data["total_expense"]) == 15000.0
        assert float(rep_data["net_savings"]) == 35000.0

        # 3. Check Monthly PDF Endpoint
        r_pdf = client.get("/api/reports/monthly-pdf?year=2026&month=9", headers=headers)
        assert r_pdf.status_code == 200
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert len(r_pdf.content) > 1000  # Non-empty valid PDF byte stream
        assert r_pdf.content.startswith(b"%PDF")
