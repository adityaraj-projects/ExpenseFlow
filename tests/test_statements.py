import os
import sys
import unittest
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient

# Add backend to sys.path
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app
from app.database.connection import get_db, sync_database_schema
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category


class TestPhonePeAndCashTransactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import time
        sync_database_schema()
        cls.client = TestClient(app)
        cls.sample_pdf_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures",
            "sample_phonepe_statement.pdf"
        )
        assert os.path.exists(cls.sample_pdf_path), f"Sample PDF not found at {cls.sample_pdf_path}"

        ts = int(time.time() * 1000)
        # Register User A with unique timestamp
        reg_a = cls.client.post("/api/auth/register", json={
            "full_name": f"Test User Alpha {ts}",
            "email": f"user_alpha_{ts}@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "currency": "INR"
        })
        cls.token_a = reg_a.json()["access_token"]
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        # Register User B with unique timestamp (for user isolation tests)
        reg_b = cls.client.post("/api/auth/register", json={
            "full_name": f"Test User Beta {ts}",
            "email": f"user_beta_{ts}@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "currency": "INR"
        })
        cls.token_b = reg_b.json()["access_token"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    def test_01_manual_cash_expense_creation(self):
        """Test recording a manual cash expense with source='cash' and transaction_time."""
        # Get user's categories
        cat_resp = self.client.get("/api/categories", headers=self.headers_a)
        self.assertEqual(cat_resp.status_code, 200)
        cats = cat_resp.json()
        exp_cat = next(c for c in cats if c["type"] == "expense")

        payload = {
            "category_id": exp_cat["id"],
            "type": "expense",
            "amount": 500.00,
            "description": "Groceries Cash Payment",
            "transaction_date": "2026-10-02",
            "transaction_time": "07:30 PM",
            "source": "cash"
        }
        res = self.client.post("/api/transactions", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source"], "cash")
        self.assertEqual(data["transaction_time"], "07:30 PM")
        self.assertEqual(float(data["amount"]), 500.00)
        self.assertEqual(data["description"], "Groceries Cash Payment")

    def test_02_manual_cash_income_creation(self):
        """Test recording manual cash income with source='cash'."""
        cat_resp = self.client.get("/api/categories", headers=self.headers_a)
        cats = cat_resp.json()
        inc_cat = next(c for c in cats if c["type"] == "income")

        payload = {
            "category_id": inc_cat["id"],
            "type": "income",
            "amount": 10000.00,
            "description": "Freelance Cash Received",
            "transaction_date": "2026-10-01",
            "transaction_time": "11:00 AM",
            "source": "cash"
        }
        res = self.client.post("/api/transactions", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source"], "cash")
        self.assertEqual(float(data["amount"]), 10000.00)

    def test_03_phonepe_pdf_parsing_and_preview(self):
        """Test uploading and parsing real PhonePe PDF statement."""
        with open(self.sample_pdf_path, "rb") as f:
            files = {"file": ("statement.pdf", f, "application/pdf")}
            res = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_a)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["statement_format"], "PhonePe PDF Statement")
        self.assertEqual(data["total_count"], 81)
        self.assertEqual(len(data["items"]), 81)

        # Verify fields of first item
        item0 = data["items"][0]
        self.assertEqual(item0["transaction_date"], "2026-10-02")
        self.assertEqual(item0["type"], "expense")  # DEBIT -> expense
        self.assertEqual(float(item0["amount"]), 30.00)
        self.assertEqual(item0["merchant_or_party"], "R A ENTERPRISE")
        self.assertEqual(item0["external_transaction_id"], "T2610021707466327727299")
        self.assertEqual(item0["external_utr"], "511919558157")
        self.assertEqual(item0["status"], "New")
        self.assertTrue(item0["is_selected"])
        self.assertFalse(item0["is_duplicate"])

        # Check an income transaction (CREDIT -> income)
        inc_item = next(it for it in data["items"] if it["type"] == "income")
        self.assertEqual(inc_item["merchant_or_party"], "KIRTI BAIRAGI BAIRAGI")
        self.assertEqual(inc_item["type"], "income")
        self.assertEqual(float(inc_item["amount"]), 621.00)
        self.assertEqual(inc_item["external_transaction_id"], "T2610011513139219078800")

    def test_04_category_suggestion_accuracy(self):
        """Verify intelligent category suggestion for merchants."""
        with open(self.sample_pdf_path, "rb") as f:
            files = {"file": ("statement.pdf", f, "application/pdf")}
            res = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_a)

        items = res.json()["items"]

        # Vikram Bhai Hostel PU should suggest Rent & Housing
        hostel_tx = next((it for it in items if "Hostel" in it["merchant_or_party"]), None)
        self.assertIsNotNone(hostel_tx)
        self.assertEqual(hostel_tx["suggested_category_name"], "Rent & Housing")

        # ekart should suggest Shopping
        ekart_tx = next((it for it in items if "ekart" in it["merchant_or_party"].lower()), None)
        self.assertIsNotNone(ekart_tx)
        self.assertEqual(ekart_tx["suggested_category_name"], "Shopping")

        # Airtel should suggest Bills & Utilities
        airtel_tx = next((it for it in items if "airtel" in it["merchant_or_party"].lower()), None)
        self.assertIsNotNone(airtel_tx)
        self.assertEqual(airtel_tx["suggested_category_name"], "Bills & Utilities")

    def test_05_partial_import_and_duplicate_detection(self):
        """Import a subset of transactions, then parse again and verify duplicate detection."""
        # 1. Parse statement
        with open(self.sample_pdf_path, "rb") as f:
            files = {"file": ("statement.pdf", f, "application/pdf")}
            res = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_a)
        items = res.json()["items"]

        # Select first 5 transactions for import
        subset = items[:5]
        import_payload = {
            "transactions": [
                {
                    "transaction_date": it["transaction_date"],
                    "transaction_time": it["transaction_time"],
                    "type": it["type"],
                    "amount": it["amount"],
                    "description": it["description"],
                    "category_id": it["suggested_category_id"],
                    "external_transaction_id": it["external_transaction_id"],
                    "external_utr": it["external_utr"],
                    "source": "phonepe"
                }
                for it in subset
            ]
        }
        import_res = self.client.post("/api/statements/import-phonepe", json=import_payload, headers=self.headers_a)
        self.assertEqual(import_res.status_code, 200)
        self.assertEqual(import_res.json()["imported_count"], 5)
        self.assertEqual(import_res.json()["skipped_count"], 0)

        # 2. Parse the statement again!
        with open(self.sample_pdf_path, "rb") as f:
            files = {"file": ("statement.pdf", f, "application/pdf")}
            res2 = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_a)
        data2 = res2.json()

        # Duplicate detection verification:
        self.assertEqual(data2["duplicate_count"], 5)
        self.assertEqual(data2["new_count"], 76)
        self.assertEqual(data2["total_count"], 81)

        # Check that the first 5 are marked Already Imported
        for it in data2["items"][:5]:
            self.assertTrue(it["is_duplicate"])
            self.assertEqual(it["status"], "Already Imported")
            self.assertFalse(it["is_selected"])

        # Check that item 6 is marked New
        self.assertFalse(data2["items"][5]["is_duplicate"])
        self.assertEqual(data2["items"][5]["status"], "New")
        self.assertTrue(data2["items"][5]["is_selected"])

    def test_06_multi_user_isolation(self):
        """User B uploading the same statement should see 0 duplicates."""
        with open(self.sample_pdf_path, "rb") as f:
            files = {"file": ("statement.pdf", f, "application/pdf")}
            res = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_b)

        data = res.json()
        self.assertEqual(data["duplicate_count"], 0)
        self.assertEqual(data["new_count"], 81)

    def test_07_transaction_source_filtering(self):
        """Verify transactions list can be filtered by source='cash' or source='phonepe'."""
        # Query cash transactions
        res_cash = self.client.get("/api/transactions?source=cash", headers=self.headers_a)
        self.assertEqual(res_cash.status_code, 200)
        cash_items = res_cash.json()["items"]
        for it in cash_items:
            self.assertIn(it["source"], ["cash", "manual"])

        # Query phonepe transactions
        res_phonepe = self.client.get("/api/transactions?source=phonepe", headers=self.headers_a)
        self.assertEqual(res_phonepe.status_code, 200)
        phonepe_items = res_phonepe.json()["items"]
        self.assertEqual(len(phonepe_items), 5)  # 5 imported earlier
        for it in phonepe_items:
            self.assertEqual(it["source"], "phonepe")

    def test_08_edit_imported_transaction_preserves_metadata(self):
        """Editing an imported transaction preserves external_transaction_id and source."""
        res_phonepe = self.client.get("/api/transactions?source=phonepe", headers=self.headers_a)
        tx = res_phonepe.json()["items"][0]
        tx_id = tx["id"]
        orig_ext_id = tx["external_transaction_id"]

        # Update description only
        up_res = self.client.put(
            f"/api/transactions/{tx_id}",
            json={"description": "Updated Merchant Note"},
            headers=self.headers_a
        )
        self.assertEqual(up_res.status_code, 200)
        updated = up_res.json()
        self.assertEqual(updated["description"], "Updated Merchant Note")
        self.assertEqual(updated["external_transaction_id"], orig_ext_id)
        self.assertEqual(updated["source"], "phonepe")

    def test_09_delete_imported_transaction(self):
        """Deleting an imported transaction removes it and updates counts."""
        res_phonepe = self.client.get("/api/transactions?source=phonepe", headers=self.headers_a)
        tx = res_phonepe.json()["items"][0]
        tx_id = tx["id"]

        del_res = self.client.delete(f"/api/transactions/{tx_id}", headers=self.headers_a)
        self.assertEqual(del_res.status_code, 200)

        # Verify not found
        get_res = self.client.get(f"/api/transactions/{tx_id}", headers=self.headers_a)
        self.assertEqual(get_res.status_code, 404)

    def test_10_reports_source_breakdown_and_filtering(self):
        """Verify report summary contains PhonePe and Cash breakdown."""
        rep_res = self.client.get("/api/reports?timeframe=this_year", headers=self.headers_a)
        self.assertEqual(rep_res.status_code, 200)
        data = rep_res.json()
        summary = data["summary"]
        self.assertIn("phonepe_income", summary)
        self.assertIn("phonepe_expense", summary)
        self.assertIn("cash_income", summary)
        self.assertIn("cash_expense", summary)

        # Filter report by source=cash
        rep_cash = self.client.get("/api/reports?timeframe=this_year&source=cash", headers=self.headers_a)
        self.assertEqual(rep_cash.status_code, 200)

    def test_11_monthly_pdf_export(self):
        """Verify downloadable monthly statement PDF is generated cleanly."""
        pdf_res = self.client.get("/api/reports/monthly-pdf?month=10&year=2026", headers=self.headers_a)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertTrue(pdf_res.content.startswith(b"%PDF"))
        self.assertGreater(len(pdf_res.content), 1000)

    def test_12_invalid_and_empty_pdf_handling(self):
        """Reject non-PDF and empty files gracefully."""
        # Non-PDF
        fake_file = {"file": ("notes.txt", b"Hello world", "text/plain")}
        res = self.client.post("/api/statements/parse-phonepe", files=fake_file, headers=self.headers_a)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Only PDF files", res.json()["detail"])

        # Empty PDF
        empty_file = {"file": ("empty.pdf", b"", "application/pdf")}
        res2 = self.client.post("/api/statements/parse-phonepe", files=empty_file, headers=self.headers_a)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("empty", res2.json()["detail"].lower())

    def test_13_dashboard_balance_and_financial_calculations(self):
        """Verify dashboard financial calculations unify Cash and PhonePe transactions seamlessly."""
        # Query current dashboard
        dash_res = self.client.get("/api/dashboard", headers=self.headers_a)
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.json()

        # Balance must equal total_income - total_expense
        summary = dash_data["summary"]
        tot_inc = float(summary["total_income"])
        tot_exp = float(summary["total_expenses"])
        bal = float(summary["total_balance"])
        self.assertAlmostEqual(bal, tot_inc - tot_exp, places=2)

    def test_14_deterministic_fingerprint_duplicate_detection(self):
        """Test duplicate detection via deterministic fingerprint when external_id is omitted."""
        cat_resp = self.client.get("/api/categories", headers=self.headers_a)
        exp_cat = next(c for c in cat_resp.json() if c["type"] == "expense")

        # Create a transaction
        tx_data = {
            "category_id": exp_cat["id"],
            "type": "expense",
            "amount": 777.00,
            "description": "Unique Local Cafe Coffee",
            "transaction_date": "2026-09-25",
            "transaction_time": "04:15 PM",
            "source": "manual"
        }
        res = self.client.post("/api/transactions", json=tx_data, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)

        # Attempt to import a transaction via bulk import with the EXACT same fingerprint
        dup_import = {
            "transactions": [
                {
                    "category_id": exp_cat["id"],
                    "type": "expense",
                    "amount": 777.00,
                    "description": "Unique Local Cafe Coffee",
                    "transaction_date": "2026-09-25",
                    "transaction_time": "04:15 PM",
                    "external_transaction_id": "",
                    "external_utr": "",
                    "source": "phonepe"
                }
            ]
        }
        imp_res = self.client.post("/api/statements/import-phonepe", json=dup_import, headers=self.headers_a)
        self.assertEqual(imp_res.status_code, 200)
        self.assertEqual(imp_res.json()["imported_count"], 0)
        self.assertEqual(imp_res.json()["skipped_count"], 1)

    def test_15_empty_valid_pdf_no_transactions(self):
        """Uploading a valid blank PDF with no statements returns friendly error."""
        import io
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf)
        doc.build([Paragraph("This is a blank document with no financial statements.", getSampleStyleSheet()['Normal'])])
        blank_pdf = buf.getvalue()

        files = {"file": ("blank.pdf", blank_pdf, "application/pdf")}
        res = self.client.post("/api/statements/parse-phonepe", files=files, headers=self.headers_a)
        self.assertEqual(res.status_code, 400)
        self.assertIn("No PhonePe transactions could be detected", res.json()["detail"])

    def test_16_user_isolation_security(self):
        """User B cannot view, update, or delete User A's transactions."""
        # Get one of User A's transactions
        txs_a = self.client.get("/api/transactions", headers=self.headers_a).json()["items"]
        self.assertGreater(len(txs_a), 0)
        target_tx_id = txs_a[0]["id"]

        # User B attempts to GET User A's transaction
        get_b = self.client.get(f"/api/transactions/{target_tx_id}", headers=self.headers_b)
        self.assertEqual(get_b.status_code, 404)

        # User B attempts to PUT User A's transaction
        put_b = self.client.put(f"/api/transactions/{target_tx_id}", json={"description": "Hacked"}, headers=self.headers_b)
        self.assertEqual(put_b.status_code, 404)

        # User B attempts to DELETE User A's transaction
        del_b = self.client.delete(f"/api/transactions/{target_tx_id}", headers=self.headers_b)
        self.assertEqual(del_b.status_code, 404)


if __name__ == "__main__":
    unittest.main()
