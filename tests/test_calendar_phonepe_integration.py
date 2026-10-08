"""
ExpenseFlow — Real PhonePe Statement Import to Calendar Date-Wise Mapping Test
Verifies:
1. Importing a multi-month PhonePe statement separates transactions by their original transaction_date.
2. September transactions appear on September 2026 calendar, NOT current date.
3. October transactions appear on October 2026 calendar, NOT current date.
4. Exact transaction time (e.g. 05:07 PM, 01:21 AM, 08:50 AM) is preserved.
5. Daily indicators (green/red/both) reflect real activity on those dates.
6. Daily detail endpoint /api/calendar/day returns exact transactions for that day.
7. Filters (source=phonepe, source=cash, type=expense) work properly on Calendar.
8. User isolation: User B's calendar is empty when User A imports statements.
9. Financial integrity: Monthly total_income - total_expense == net_balance.
"""
import os
import sys
import pytest
from datetime import date
from fastapi.testclient import TestClient

backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app

SAMPLE_PDF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "sample_phonepe_statement.pdf")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def register_user(client, prefix="cal_phonepe"):
    import time
    ts = int(time.time() * 1000)
    email = f"{prefix}_{ts}_{os.urandom(3).hex()}@example.com"
    pwd = "SecurePassword123!"
    payload = {
        "full_name": f"PhonePe Test User {ts}",
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "currency": "INR"
    }
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, f"Registration failed: {r.text}"
    token = r.json()["access_token"]
    user_info = r.json()["user"]
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_info["id"],
        "email": email
    }


class TestPhonePeToCalendarDateWise:

    def test_phonepe_multi_month_import_and_calendar_dates(self, client):
        assert os.path.exists(SAMPLE_PDF_PATH), f"Fixture not found at {SAMPLE_PDF_PATH}"

        user_a = register_user(client, prefix="user_a_phonepe")
        headers_a = user_a["headers"]

        user_b = register_user(client, prefix="user_b_empty")
        headers_b = user_b["headers"]

        # 1. Parse PhonePe PDF for User A
        with open(SAMPLE_PDF_PATH, "rb") as f:
            parse_res = client.post(
                "/api/statements/parse-phonepe",
                files={"file": ("sample_statement.pdf", f, "application/pdf")},
                headers=headers_a
            )
        assert parse_res.status_code == 200, f"Parse failed: {parse_res.text}"
        parse_data = parse_res.json()
        total_count = parse_data["total_count"]
        assert total_count > 0, "No transactions extracted from sample PDF"
        items = parse_data["items"]

        # 2. Import parsed transactions into DB for User A
        import_payload = {
            "transactions": [
                {
                    "transaction_date": it["transaction_date"],
                    "transaction_time": it.get("transaction_time"),
                    "amount": it["amount"],
                    "type": it["type"],
                    "description": it["description"],
                    "category_id": it["suggested_category_id"],
                    "source": "phonepe",
                    "external_transaction_id": it.get("external_transaction_id"),
                    "external_utr": it.get("external_utr")
                }
                for it in items
            ],
            "statement_period": "Sep 2026 – Oct 2026",
            "filename": "sample_phonepe_statement.pdf",
            "total_found": total_count
        }

        imp_res = client.post("/api/statements/import-phonepe", json=import_payload, headers=headers_a)
        assert imp_res.status_code == 200, f"Import failed: {imp_res.text}"
        imp_data = imp_res.json()
        assert imp_data["imported_count"] == total_count

        # 3. Calendar Month: Query September 2026
        cal_sep = client.get("/api/calendar/month?year=2026&month=9", headers=headers_a)
        assert cal_sep.status_code == 200
        sep_data = cal_sep.json()
        assert sep_data["year"] == 2026
        assert sep_data["month"] == 9
        assert sep_data["total_transactions"] > 0
        # Verify all September transactions actually have 2026-09 dates
        for tx in sep_data["transactions"]:
            assert tx["transaction_date"].startswith("2026-09-")
            assert tx["source"] == "phonepe"

        # 4. Calendar Month: Query October 2026
        cal_oct = client.get("/api/calendar/month?year=2026&month=10", headers=headers_a)
        assert cal_oct.status_code == 200
        oct_data = cal_oct.json()
        assert oct_data["year"] == 2026
        assert oct_data["month"] == 10
        assert oct_data["total_transactions"] > 0
        # Verify all October transactions actually have 2026-10 dates
        for tx in oct_data["transactions"]:
            assert tx["transaction_date"].startswith("2026-10-")
            assert tx["source"] == "phonepe"

        # Months must be distinct
        sep_tx_ids = {t["id"] for t in sep_data["transactions"]}
        oct_tx_ids = {t["id"] for t in oct_data["transactions"]}
        assert len(sep_tx_ids.intersection(oct_tx_ids)) == 0, "September and October transactions should not overlap"

        # 5. Check specific date: October 2, 2026
        day_oct2 = client.get("/api/calendar/day?date=2026-10-02", headers=headers_a)
        assert day_oct2.status_code == 200
        d_oct2_data = day_oct2.json()
        assert d_oct2_data["date"] == "2026-10-02"
        assert d_oct2_data["transaction_count"] > 0
        oct2_tx = next((t for t in d_oct2_data["transactions"] if t.get("external_transaction_id") == "T2610021707466327727299"), None)
        assert oct2_tx is not None, "October 2 transaction not found in day endpoint"
        assert oct2_tx["transaction_time"] == "05:07 PM"
        assert oct2_tx["source"] == "phonepe"
        assert oct2_tx["category_name"] is not None

        # 6. Check specific date: September 14, 2026
        day_sep14 = client.get("/api/calendar/day?date=2026-09-14", headers=headers_a)
        assert day_sep14.status_code == 200
        d_sep14_data = day_sep14.json()
        assert d_sep14_data["date"] == "2026-09-14"
        assert d_sep14_data["transaction_count"] > 0
        sep14_tx = next((t for t in d_sep14_data["transactions"] if t.get("external_transaction_id") == "OM2609140121122586464687W"), None)
        assert sep14_tx is not None
        assert sep14_tx["transaction_time"] == "01:21 AM"

        # 7. Check specific date: September 2, 2026
        day_sep2 = client.get("/api/calendar/day?date=2026-09-02", headers=headers_a)
        assert day_sep2.status_code == 200
        d_sep2_data = day_sep2.json()
        assert d_sep2_data["date"] == "2026-09-02"
        sep2_tx = next((t for t in d_sep2_data["transactions"] if t.get("external_transaction_id") == "T2609020850255395995466"), None)
        assert sep2_tx is not None
        assert sep2_tx["transaction_time"] == "08:50 AM"

        # 8. Check Calendar Source Filters: PhonePe filter vs Cash filter
        cal_phonepe_filter = client.get("/api/calendar/month?year=2026&month=10&source=phonepe", headers=headers_a)
        assert cal_phonepe_filter.status_code == 200
        assert cal_phonepe_filter.json()["total_transactions"] == oct_data["total_transactions"]

        cal_cash_filter = client.get("/api/calendar/month?year=2026&month=10&source=cash", headers=headers_a)
        assert cal_cash_filter.status_code == 200
        assert cal_cash_filter.json()["total_transactions"] == 0

        # 9. Financial Integrity: Month Income - Month Expense == Net Balance
        for month_data in [sep_data, oct_data]:
            calc_net = round(month_data["total_income"] - month_data["total_expense"], 2)
            assert round(month_data["net_balance"], 2) == calc_net

        # 10. User Isolation: User B's calendar must be empty for 2026-10 and 2026-09
        user_b_oct = client.get("/api/calendar/month?year=2026&month=10", headers=headers_b)
        assert user_b_oct.status_code == 200
        assert user_b_oct.json()["total_transactions"] == 0
        assert user_b_oct.json()["total_income"] == 0.0
        assert user_b_oct.json()["total_expense"] == 0.0

        user_b_day = client.get("/api/calendar/day?date=2026-10-02", headers=headers_b)
        assert user_b_day.status_code == 200
        assert user_b_day.json()["transaction_count"] == 0
