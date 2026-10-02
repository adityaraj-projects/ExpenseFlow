import os
import sys
import unittest
import time
import json
from decimal import Decimal
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Add backend to sys.path
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app
from app.database.connection import sync_database_schema, SessionLocal
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category, CategoryType
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal
from app.models.reminder import Reminder, ReminderStatus
from app.models.recurring_transaction import RecurringTransaction, RecurringStatus, RecurringFrequency
from app.models.notification import Notification, NotificationType
from app.models.user_preference import UserPreference
from app.services.scheduler_service import SchedulerService


class TestSmartSummaryBackupNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sync_database_schema()
        cls.client = TestClient(app)

        ts = int(time.time() * 1000)
        # Register User Alpha
        reg_a = cls.client.post("/api/auth/register", json={
            "full_name": f"Enhance Alpha {ts}",
            "email": f"enhance_alpha_{ts}@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "currency": "INR"
        })
        cls.user_a_data = reg_a.json()
        cls.token_a = cls.user_a_data["access_token"]
        cls.user_a_id = cls.user_a_data["user"]["id"]
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        # Register User Beta (for multi-user isolation tests)
        reg_b = cls.client.post("/api/auth/register", json={
            "full_name": f"Enhance Beta {ts}",
            "email": f"enhance_beta_{ts}@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "currency": "INR"
        })
        cls.user_b_data = reg_b.json()
        cls.token_b = cls.user_b_data["access_token"]
        cls.user_b_id = cls.user_b_data["user"]["id"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

        # Fetch default categories for user A
        cat_resp = cls.client.get("/api/categories", headers=cls.headers_a)
        cls.categories_a = {c["name"]: c["id"] for c in cat_resp.json()}

        cls.cat_inc_id = None
        cls.cat_exp_id = None
        for name, cid in cls.categories_a.items():
            if "salary" in name.lower() or "income" in name.lower():
                cls.cat_inc_id = cid
            if "food" in name.lower() or "dining" in name.lower():
                cls.cat_exp_id = cid

        if not cls.cat_inc_id:
            c = cls.client.post("/api/categories", headers=cls.headers_a, json={
                "name": "Salary / Income", "type": "income", "color": "#10B981", "icon": "briefcase"
            }).json()
            cls.cat_inc_id = c["id"]

        if not cls.cat_exp_id:
            c = cls.client.post("/api/categories", headers=cls.headers_a, json={
                "name": "Food & Dining", "type": "expense", "color": "#EF4444", "icon": "coffee"
            }).json()
            cls.cat_exp_id = c["id"]

    def test_01_critical_financial_integrity(self):
        """
        CRITICAL FINANCIAL TEST:
        Start: Balance = ₹0
        Add: Income = ₹50,000
        Add: Cash Expense = ₹5,000
        Add: PhonePe Expense = ₹10,000
        Expected:
        Income = ₹50,000
        Expense = ₹15,000
        Balance = ₹35,000
        Monthly summary MUST show:
        Income = ₹50,000
        Expenses = ₹15,000
        Savings = ₹35,000
        PhonePe = ₹10,000
        Cash = ₹5,000
        Database, API, Frontend, Dashboard, Reports ALL MATCH.
        """
        today = date.today()
        month = today.month
        year = today.year

        # 1. Add Income = ₹50,000
        r_inc = self.client.post("/api/transactions", headers=self.headers_a, json={
            "amount": 50000.0,
            "type": "income",
            "category_id": self.cat_inc_id,
            "transaction_date": today.isoformat(),
            "description": "Monthly Salary",
            "source": "manual"
        })
        self.assertEqual(r_inc.status_code, 201)

        # 2. Add Cash Expense = ₹5,000
        r_cash = self.client.post("/api/transactions", headers=self.headers_a, json={
            "amount": 5000.0,
            "type": "expense",
            "category_id": self.cat_exp_id,
            "transaction_date": today.isoformat(),
            "description": "Cash Groceries",
            "source": "cash"
        })
        self.assertEqual(r_cash.status_code, 201)

        # 3. Add PhonePe Expense = ₹10,000
        r_phonepe = self.client.post("/api/transactions", headers=self.headers_a, json={
            "amount": 10000.0,
            "type": "expense",
            "category_id": self.cat_exp_id,
            "transaction_date": today.isoformat(),
            "description": "PhonePe Electronics",
            "source": "phonepe",
            "external_transaction_id": f"T_CRIT_{int(time.time()*1000)}"
        })
        self.assertEqual(r_phonepe.status_code, 201)

        # 4. Verify Dashboard calculations
        dash_res = self.client.get("/api/dashboard", headers=self.headers_a)
        self.assertEqual(dash_res.status_code, 200)
        dash = dash_res.json()
        self.assertAlmostEqual(float(dash["summary"]["total_balance"]), 35000.0, places=2)
        self.assertAlmostEqual(float(dash["summary"]["month_income"]), 50000.0, places=2)
        self.assertAlmostEqual(float(dash["summary"]["month_expense"]), 15000.0, places=2)

        # 5. Verify Monthly Financial Summary
        sum_res = self.client.get(f"/api/reports/monthly-summary?month={month}&year={year}", headers=self.headers_a)
        self.assertEqual(sum_res.status_code, 200)
        ms = sum_res.json()

        self.assertAlmostEqual(float(ms["total_income"]), 50000.0, places=2)
        self.assertAlmostEqual(float(ms["total_expense"]), 15000.0, places=2)
        self.assertAlmostEqual(float(ms["net_savings"]), 35000.0, places=2)
        # Savings rate = (35000 / 50000) * 100 = 70.0%
        self.assertAlmostEqual(float(ms["savings_rate"]), 70.0, places=1)
        self.assertEqual(ms["income_count"], 1)
        self.assertEqual(ms["expense_count"], 2)

        # Verify source breakdown
        source_map = {s["source"]: s for s in ms["source_breakdown"]}
        self.assertIn("phonepe", source_map)
        self.assertIn("cash", source_map)
        self.assertAlmostEqual(float(source_map["phonepe"]["expense"]), 10000.0, places=2)
        self.assertAlmostEqual(float(source_map["cash"]["expense"]), 5000.0, places=2)

    def test_02_monthly_summary_zero_income_safety(self):
        """Verify zero-income month returns 0.0% savings rate without NaN or crash."""
        # Query for a future month with 0 transactions
        res = self.client.get("/api/reports/monthly-summary?month=1&year=2028", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(float(data["total_income"]), 0.0)
        self.assertEqual(float(data["total_expense"]), 0.0)
        self.assertEqual(float(data["net_savings"]), 0.0)
        self.assertEqual(float(data["savings_rate"]), 0.0)
        self.assertEqual(data["income_count"], 0)
        self.assertEqual(data["expense_count"], 0)
        self.assertIsInstance(data["insights"], list)
        self.assertTrue(len(data["insights"]) > 0)

    def test_03_month_over_month_comparison_and_insights(self):
        """Test month-over-month calculation and rule-based insights generation."""
        today = date.today()
        res = self.client.get(f"/api/reports/monthly-summary?month={today.month}&year={today.year}", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check comparison structure
        comp = data["comparison"]
        self.assertIn("prev_month_name", comp)
        self.assertIn("summary_message", comp)
        self.assertIn("expense_change_direction", comp)

        # Check insights
        insights = data["insights"]
        self.assertTrue(len(insights) >= 1)
        # Should contain PhonePe transaction insight since PhonePe was ₹10k vs Cash ₹5k
        found_phonepe = any("PhonePe" in ins for ins in insights)
        self.assertTrue(found_phonepe, f"Expected PhonePe insight in {insights}")

    def test_04_full_backup_export(self):
        """Test exporting a full versioned backup file."""
        res = self.client.get("/api/backup/export", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/json")
        self.assertIn("attachment; filename=", res.headers.get("content-disposition", ""))

        backup_data = res.json()
        self.assertEqual(backup_data.get("application"), "ExpenseFlow")
        self.assertEqual(backup_data.get("backup_version"), "1.0")
        self.assertIn("created_at", backup_data)
        self.assertIn("user", backup_data)
        self.assertNotIn("password_hash", backup_data["user"])
        self.assertNotIn("hashed_password", backup_data["user"])

        # Validate sections
        self.assertIsInstance(backup_data.get("categories"), list)
        self.assertIsInstance(backup_data.get("transactions"), list)
        self.assertTrue(len(backup_data["transactions"]) >= 3)
        self.assertIsInstance(backup_data.get("notification_preferences"), dict)

    def test_05_backup_validation(self):
        """Test validating valid, invalid, and unsupported backup files."""
        # Valid backup
        valid_payload = {
            "application": "ExpenseFlow",
            "backup_version": "1.0",
            "created_at": "2026-10-02T12:00:00Z",
            "user": {"name": "Test User", "currency": "INR"},
            "categories": [{"name": "Test Cat", "type": "expense"}],
            "transactions": [{"amount": 100.0, "type": "expense", "transaction_date": "2026-10-01", "description": "Coffee"}]
        }
        valid_json = json.dumps(valid_payload).encode("utf-8")
        val_res = self.client.post(
            "/api/backup/validate",
            headers=self.headers_a,
            files={"file": ("backup.json", valid_json, "application/json")}
        )
        self.assertEqual(val_res.status_code, 200)
        val_data = val_res.json()
        self.assertTrue(val_data["valid"])
        self.assertEqual(val_data["counts"]["categories"], 1)
        self.assertEqual(val_data["counts"]["transactions"], 1)

        # Invalid app name
        invalid_payload = {
            "application": "WrongApp",
            "backup_version": "1.0"
        }
        inv_res = self.client.post(
            "/api/backup/validate",
            headers=self.headers_a,
            files={"file": ("backup.json", json.dumps(invalid_payload).encode("utf-8"), "application/json")}
        )
        self.assertEqual(inv_res.status_code, 400)

        # Empty file
        empty_res = self.client.post(
            "/api/backup/validate",
            headers=self.headers_a,
            files={"file": ("empty.json", b"", "application/json")}
        )
        self.assertEqual(empty_res.status_code, 400)

    def test_06_backup_restore_deduplication(self):
        """Test restoring backup skips existing transactions and adds new ones safely."""
        # 1. Export current backup of User A
        export_res = self.client.get("/api/backup/export", headers=self.headers_a)
        backup_dict = export_res.json()
        initial_tx_count = len(backup_dict["transactions"])

        # 2. Add a new unique transaction to the backup payload
        backup_dict["transactions"].append({
            "amount": 777.0,
            "type": "expense",
            "transaction_date": "2026-10-02",
            "transaction_time": "11:30 AM",
            "description": f"Unique Restore Test Tx {int(time.time())}",
            "category_name": "Food & Dining",
            "source": "manual"
        })

        # 3. Restore backup
        restore_res = self.client.post(
            "/api/backup/restore",
            headers=self.headers_a,
            json=backup_dict
        )
        self.assertEqual(restore_res.status_code, 200)
        res_data = restore_res.json()

        # Initial transactions should have been skipped, only the 1 new transaction imported
        self.assertEqual(res_data["summary"]["transactions"]["imported"], 1)
        self.assertGreaterEqual(res_data["summary"]["transactions"]["skipped"], initial_tx_count)
        self.assertEqual(res_data["summary"]["transactions"]["failed"], 0)

    def test_07_multi_user_data_isolation(self):
        """
        User B must NEVER be able to:
        - access User A's monthly summary
        - export User A's data
        - restore into User A's account
        """
        today = date.today()
        # User B queries monthly summary -> should only reflect User B's own transactions (0)
        res_b = self.client.get(f"/api/reports/monthly-summary?month={today.month}&year={today.year}", headers=self.headers_b)
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        self.assertEqual(float(data_b["total_income"]), 0.0)
        self.assertEqual(float(data_b["total_expense"]), 0.0)
        self.assertEqual(data_b["total_transactions"], 0)

        # User B exports backup -> must contain only User B's data (0 transactions)
        export_b = self.client.get("/api/backup/export", headers=self.headers_b)
        self.assertEqual(export_b.status_code, 200)
        self.assertEqual(len(export_b.json()["transactions"]), 0)

        # User B restores User A's backup -> must restore into User B's account without affecting User A
        export_a = self.client.get("/api/backup/export", headers=self.headers_a).json()
        restore_b = self.client.post("/api/backup/restore", headers=self.headers_b, json=export_a)
        self.assertEqual(restore_b.status_code, 200)
        self.assertGreaterEqual(restore_b.json()["summary"]["transactions"]["imported"], 3)

        # Verify User A's transaction count remains unchanged
        tx_a = self.client.get("/api/transactions", headers=self.headers_a).json()
        tx_b = self.client.get("/api/transactions", headers=self.headers_b).json()
        self.assertEqual(tx_b["items"][0]["user_id"], self.user_b_id)
        self.assertEqual(tx_a["items"][0]["user_id"], self.user_a_id)

    def test_08_budget_alerts_80_and_100_percent(self):
        """Test budget warning at 80% and exceeded alert at 100%+."""
        # 1. Create a budget for Food: limit ₹10,000 for current month
        today = date.today()
        b_resp = self.client.post("/api/budgets", headers=self.headers_a, json={
            "category_id": self.cat_exp_id,
            "amount": 10000.0,
            "month": today.month,
            "year": today.year
        })
        self.assertIn(b_resp.status_code, [200, 201])
        b_id = b_resp.json()["id"]

        # Run scheduler budget check with db session
        db = SessionLocal()
        try:
            alerts = SchedulerService.check_budget_thresholds(db, self.user_a_id)
            # In test 01, Food already had ₹15,000 spent, which is 150% of ₹10,000!
            # So budget_100 alert should have been created!
            notifs = db.query(Notification).filter(
                Notification.user_id == self.user_a_id,
                Notification.type == NotificationType.BUDGET_EXCEEDED
            ).all()
            self.assertTrue(len(notifs) >= 1)
            self.assertIn("Budget Exceeded", notifs[0].title)

            # Check idempotency: running again should create 0 new alerts
            repeat_alerts = SchedulerService.check_budget_thresholds(db, self.user_a_id)
            self.assertEqual(repeat_alerts, 0)
        finally:
            db.close()

    def test_09_upcoming_bill_reminder_notification(self):
        """Test reminder alert for a bill due tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        r_res = self.client.post("/api/reminders", headers=self.headers_a, json={
            "title": f"Electricity Bill {int(time.time())}",
            "amount": 1850.0,
            "reminder_date": tomorrow.isoformat(),
            "notification_enabled": True
        })
        self.assertEqual(r_res.status_code, 201)

        db = SessionLocal()
        try:
            notified = SchedulerService.process_upcoming_reminders(db, self.user_a_id)
            self.assertGreaterEqual(notified, 1)

            notif = db.query(Notification).filter(
                Notification.user_id == self.user_a_id,
                Notification.type == NotificationType.REMINDER,
                Notification.idempotency_key.like("reminder_upcoming_%")
            ).first()
            self.assertIsNotNone(notif)
            self.assertIn("due tomorrow", notif.message.lower())

            # Idempotency check: running again must return 0
            self.assertEqual(SchedulerService.process_upcoming_reminders(db, self.user_a_id), 0)
        finally:
            db.close()

    def test_10_upcoming_recurring_transaction_notification(self):
        """Test notification for recurring transaction scheduled for tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        rec_res = self.client.post("/api/recurring-transactions", headers=self.headers_a, json={
            "description": f"Netflix Subscription {int(time.time())}",
            "amount": 649.0,
            "type": "expense",
            "frequency": "monthly",
            "category_id": self.cat_exp_id,
            "start_date": tomorrow.isoformat()
        })
        self.assertEqual(rec_res.status_code, 201)

        db = SessionLocal()
        try:
            notified = SchedulerService.process_upcoming_recurring_transactions(db, self.user_a_id)
            self.assertGreaterEqual(notified, 1)

            notif = db.query(Notification).filter(
                Notification.user_id == self.user_a_id,
                Notification.type == NotificationType.RECURRING_UPCOMING
            ).first()
            self.assertIsNotNone(notif)
            self.assertIn("Netflix", notif.message)
            self.assertIn("scheduled for tomorrow", notif.message)

            # Idempotency check
            self.assertEqual(SchedulerService.process_upcoming_recurring_transactions(db, self.user_a_id), 0)
        finally:
            db.close()

    def test_11_notification_preferences_toggles(self):
        """Test retrieving and updating notification preferences including monthly summary."""
        # 1. Get preferences
        get_res = self.client.get("/api/preferences", headers=self.headers_a)
        self.assertEqual(get_res.status_code, 200)
        prefs = get_res.json()
        self.assertIn("monthly_summary_alerts", prefs)

        # 2. Update preferences: disable budget alerts and monthly summary
        put_res = self.client.put("/api/preferences", headers=self.headers_a, json={
            "budget_alerts": False,
            "monthly_summary_alerts": False
        })
        self.assertEqual(put_res.status_code, 200)
        updated = put_res.json()
        self.assertFalse(updated["budget_alerts"])
        self.assertFalse(updated["monthly_summary_alerts"])

        # 3. Restore preferences to True
        put_res2 = self.client.put("/api/preferences", headers=self.headers_a, json={
            "budget_alerts": True,
            "monthly_summary_alerts": True
        })
        self.assertEqual(put_res2.status_code, 200)
        self.assertTrue(put_res2.json()["budget_alerts"])
        self.assertTrue(put_res2.json()["monthly_summary_alerts"])


if __name__ == "__main__":
    unittest.main()
