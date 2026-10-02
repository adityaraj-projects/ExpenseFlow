import sys
import time
import json
from decimal import Decimal
from datetime import date, timedelta
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://expenseflow-3zl0.onrender.com/api"

class TestLogger:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.records = []

    def record(self, section, name, status, details=""):
        if status == "PASS":
            self.passed += 1
            icon = "[PASS]"
        else:
            self.failed += 1
            icon = "[FAIL]"
        msg = f"{icon} [{section}] {name}: {details}"
        print(msg, flush=True)
        self.records.append({
            "section": section,
            "name": name,
            "status": status,
            "details": details
        })

logger = TestLogger()

def api_call(endpoint, method="GET", data=None, token=None, timeout=35):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            st = resp.getcode()
            raw = resp.read().decode("utf-8")
            return st, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except Exception as e:
        return 500, {"error": str(e)}

print("=== STARTING FINAL FUNCTIONAL & FINANCIAL INTEGRITY REGRESSION SUITE ===", flush=True)
ts = int(time.time())

# 1. Warm up & Health check
print("Warming up cloud backend...", flush=True)
for attempt in range(3):
    st, health = api_call("/health", timeout=45)
    if st == 200 and health.get("database_connected") is True:
        break
    time.sleep(3)

if st == 200 and health.get("database_connected") is True:
    logger.record("System Health", "FastAPI & MySQL Connectivity", "PASS", f"Status: {health.get('status')}")
else:
    logger.record("System Health", "FastAPI & MySQL Connectivity", "FAIL", str(health))

# 2. Register User A
user_a_email = f"qa_reg_a_{ts}@expenseflow.com"
password = "Password123!"
reg_a = {
    "full_name": "Final QA User A",
    "email": user_a_email,
    "password": password,
    "confirm_password": password,
    "currency": "INR"
}
st, res_a = api_call("/auth/register", method="POST", data=reg_a)
if st == 201 and "access_token" in res_a:
    token_a = res_a["access_token"]
    user_a_id = res_a["user"]["id"]
    logger.record("Auth", "User A Registration", "PASS", f"User ID: {user_a_id}")
else:
    logger.record("Auth", "User A Registration", "FAIL", str(res_a))
    sys.exit(1)

# 3. User A Login
st, login_a = api_call("/auth/login", method="POST", data={"email": user_a_email, "password": password})
if st == 200 and "access_token" in login_a:
    logger.record("Auth", "User A Login", "PASS", "JWT issued successfully")
else:
    logger.record("Auth", "User A Login", "FAIL", str(login_a))

# 4. User A Initial Clean Balance Verification (Expected 0.00)
st, dash_init = api_call("/dashboard", token=token_a)
init_bal = Decimal(str(dash_init["summary"]["total_balance"]))
if init_bal == Decimal("0.00"):
    logger.record("Financial Integrity", "Initial Clean Balance is ₹0.00", "PASS", f"Balance: ₹{init_bal}")
else:
    logger.record("Financial Integrity", "Initial Clean Balance", "FAIL", f"Expected 0.00, got {init_bal}")

# Fetch User A's default seeded categories
st, cats_a = api_call("/categories", token=token_a)
salary_cat = next((c for c in cats_a if c["name"] == "Salary"), None)
food_cat = next((c for c in cats_a if c["name"] == "Food & Dining"), None)
salary_cat_id = salary_cat["id"]
food_cat_id = food_cat["id"]

# 5. Add Income: ₹50,000 -> Expected Balance ₹50,000
today_str = str(date.today())
st, tx_inc1 = api_call("/transactions", method="POST", data={
    "category_id": salary_cat_id,
    "type": "income",
    "amount": 50000.0,
    "description": "Monthly Salary QA",
    "transaction_date": today_str
}, token=token_a)
st, dash1 = api_call("/dashboard", token=token_a)
bal1 = Decimal(str(dash1["summary"]["total_balance"]))
inc1 = Decimal(str(dash1["summary"]["total_income"]))
if bal1 == Decimal("50000.00") and inc1 == Decimal("50000.00"):
    logger.record("Financial Integrity", "Add Income ₹50,000 (Balance = ₹50,000)", "PASS", f"Balance: ₹{bal1}, Income: ₹{inc1}")
else:
    logger.record("Financial Integrity", "Add Income ₹50,000", "FAIL", f"Expected 50000, got {bal1}")

# 6. Add Expense: ₹10,000 -> Expected Balance ₹40,000
st, tx_exp1 = api_call("/transactions", method="POST", data={
    "category_id": food_cat_id,
    "type": "expense",
    "amount": 10000.0,
    "description": "Grocery Spend QA",
    "transaction_date": today_str
}, token=token_a)
st, dash2 = api_call("/dashboard", token=token_a)
bal2 = Decimal(str(dash2["summary"]["total_balance"]))
exp2 = Decimal(str(dash2["summary"]["total_expenses"]))
if bal2 == Decimal("40000.00") and exp2 == Decimal("10000.00"):
    logger.record("Financial Integrity", "Add Expense ₹10,000 (Balance = ₹40,000)", "PASS", f"Balance: ₹{bal2}, Expense: ₹{exp2}")
else:
    logger.record("Financial Integrity", "Add Expense ₹10,000", "FAIL", f"Expected 40000, got {bal2}")

# 7. Add Another Expense: ₹5,000 -> Expected Balance ₹35,000
st, tx_exp2 = api_call("/transactions", method="POST", data={
    "category_id": food_cat_id,
    "type": "expense",
    "amount": 5000.0,
    "description": "Dinner Spend QA",
    "transaction_date": today_str
}, token=token_a)
tx_exp2_id = tx_exp2["id"]
st, dash3 = api_call("/dashboard", token=token_a)
bal3 = Decimal(str(dash3["summary"]["total_balance"]))
exp3 = Decimal(str(dash3["summary"]["total_expenses"]))
if bal3 == Decimal("35000.00") and exp3 == Decimal("15000.00"):
    logger.record("Financial Integrity", "Add Expense ₹5,000 (Balance = ₹35,000)", "PASS", f"Balance: ₹{bal3}, Expense: ₹{exp3}")
else:
    logger.record("Financial Integrity", "Add Expense ₹5,000", "FAIL", f"Expected 35000, got {bal3}")

# 8. Edit ₹5,000 Expense to ₹7,000 -> Expected Balance ₹33,000
st, edit_res = api_call(f"/transactions/{tx_exp2_id}", method="PUT", data={
    "amount": 7000.0
}, token=token_a)
st, dash4 = api_call("/dashboard", token=token_a)
bal4 = Decimal(str(dash4["summary"]["total_balance"]))
exp4 = Decimal(str(dash4["summary"]["total_expenses"]))
if bal4 == Decimal("33000.00") and exp4 == Decimal("17000.00"):
    logger.record("Financial Integrity", "Edit Expense ₹5k->₹7k (Balance = ₹33,000)", "PASS", f"Balance: ₹{bal4}, Expense: ₹{exp4}")
else:
    logger.record("Financial Integrity", "Edit Expense ₹5k->₹7k", "FAIL", f"Expected 33000, got {bal4}")

# 9. Delete the ₹7,000 Expense -> Expected Balance ₹40,000
st, del_res = api_call(f"/transactions/{tx_exp2_id}", method="DELETE", token=token_a)
st, dash5 = api_call("/dashboard", token=token_a)
bal5 = Decimal(str(dash5["summary"]["total_balance"]))
exp5 = Decimal(str(dash5["summary"]["total_expenses"]))
if bal5 == Decimal("40000.00") and exp5 == Decimal("10000.00"):
    logger.record("Financial Integrity", "Delete ₹7k Expense (Balance = ₹40,000)", "PASS", f"Balance: ₹{bal5}, Expense: ₹{exp5}")
else:
    logger.record("Financial Integrity", "Delete ₹7k Expense", "FAIL", f"Expected 40000, got {bal5}")

# 10. Category Creation: Custom Expense Category & Custom Income Category
st, cat_exp = api_call("/categories", method="POST", data={
    "name": "Cloud Hosting & AI",
    "type": "expense",
    "icon": "server",
    "color": "#6366F1"
}, token=token_a)
cat_exp_id = cat_exp["id"]

st, cat_inc = api_call("/categories", method="POST", data={
    "name": "Consulting Advisory",
    "type": "income",
    "icon": "briefcase",
    "color": "#10B981"
}, token=token_a)
cat_inc_id = cat_inc["id"]

if st == 201 and cat_exp.get("name") == "Cloud Hosting & AI" and cat_inc.get("name") == "Consulting Advisory":
    logger.record("Category Management", "Create Expense & Income Categories", "PASS", f"Expense ID: {cat_exp_id}, Income ID: {cat_inc_id}")
else:
    logger.record("Category Management", "Create Expense & Income Categories", "FAIL", f"Exp: {cat_exp}, Inc: {cat_inc}")

# 11. Create Monthly Budget & Add Expense Against It
cur_m = date.today().month
cur_y = date.today().year
st, b_created = api_call("/budgets", method="POST", data={
    "category_id": cat_exp_id,
    "amount": 8000.0,
    "month": cur_m,
    "year": cur_y
}, token=token_a)

# Add expense of ₹4,000 under Cloud Hosting (50% usage -> safe)
st, tx_b1 = api_call("/transactions", method="POST", data={
    "category_id": cat_exp_id,
    "type": "expense",
    "amount": 4000.0,
    "description": "AWS Hosting Bill",
    "transaction_date": today_str
}, token=token_a)

st, b_sum1 = api_call(f"/budgets?month={cur_m}&year={cur_y}", token=token_a)
b_item1 = next((b for b in b_sum1.get("items", []) if b["category_id"] == cat_exp_id), None)
if b_item1 and b_item1["percentage_used"] == 50.0 and b_item1["status"] == "safe":
    logger.record("Budget Management", "Budget Creation & 50% Spent Progress (Safe)", "PASS", f"Spent: ₹{b_item1['spent_amount']}, Usage: {b_item1['percentage_used']}%, Status: {b_item1['status']}")
else:
    logger.record("Budget Management", "Budget Creation & Progress", "FAIL", str(b_item1))

# 12. Create Savings Goal & Deposit / Withdraw
st, goal_res = api_call("/goals", method="POST", data={
    "name": "Japan Tech Tour",
    "target_amount": 200000.0,
    "initial_amount": 0.0,
    "target_date": str(date.today() + timedelta(days=365)),
    "description": "Tokyo Akihabara & Robotics"
}, token=token_a)
goal_id = goal_res["id"]

# Deposit ₹50,000 (25%)
st, g_dep = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 50000.0, "action": "deposit"}, token=token_a)
# Withdraw ₹10,000 (20% remaining)
st, g_with = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 10000.0, "action": "withdraw"}, token=token_a)
curr_val = Decimal(str(g_with["current_amount"]))
pct_val = g_with["progress_percentage"]
if curr_val == Decimal("40000.00") and pct_val == 20.0:
    logger.record("Savings Goals", "Goal Creation, Deposit & Withdrawal Progress", "PASS", f"Current: ₹{curr_val} (20.0%)")
else:
    logger.record("Savings Goals", "Savings Goals Lifecycle", "FAIL", f"Expected 40000 (20%), got {curr_val} ({pct_val}%)")

# 13. Reports & Analytics
st, rep = api_call("/reports?timeframe=this_month", token=token_a)
rep_summary = rep.get("summary", {})
if st == 200 and "total_income" in rep_summary and "total_expense" in rep_summary:
    logger.record("Reports & Analytics", "Monthly Report Aggregates & Timeline Series", "PASS", f"Income: ₹{rep_summary['total_income']}, Expense: ₹{rep_summary['total_expense']}, Savings: ₹{rep_summary['net_savings']}")
else:
    logger.record("Reports & Analytics", "Monthly Report Aggregates", "FAIL", str(rep))

# 14. Payment Reminders
st, rem_created = api_call("/reminders", method="POST", data={
    "title": "Apartment Rent Due",
    "amount": 15000.0,
    "category_id": food_cat_id,
    "reminder_date": str(date.today() + timedelta(days=5)),
    "reminder_time": "10:00",
    "recurrence": "monthly"
}, token=token_a)
rem_id = rem_created.get("id")
st, rem_list = api_call("/reminders", token=token_a)
has_rem = isinstance(rem_list, list) and any(r["id"] == rem_id for r in rem_list)
if st == 200 and has_rem:
    logger.record("Payment Reminders", "Create & Retrieve Reminder", "PASS", f"Reminder ID: {rem_id}")
else:
    logger.record("Payment Reminders", "Create & Retrieve Reminder", "FAIL", str(rem_list))

# 15. Recurring Transactions
st_rec, rec_created = api_call("/recurring-transactions", method="POST", data={
    "description": "Fibre Internet Subscription",
    "amount": 999.0,
    "type": "expense",
    "category_id": cat_exp_id,
    "frequency": "monthly",
    "start_date": today_str
}, token=token_a)
rec_id = rec_created.get("id") if isinstance(rec_created, dict) else None
st_list, rec_list = api_call("/recurring-transactions", token=token_a)
has_rec = isinstance(rec_list, list) and any(r.get("id") == rec_id for r in rec_list)
if st_rec == 201 and has_rec:
    logger.record("Recurring Transactions", "Create & Retrieve Recurring Rule", "PASS", f"Rule ID: {rec_id}")
else:
    logger.record("Recurring Transactions", "Create & Retrieve Recurring Rule", "FAIL", f"Create: {st_rec} {rec_created}, List: {st_list} {rec_list}")

# 16. In-App Notifications
st, notif_list = api_call("/notifications", token=token_a)
if st == 200 and isinstance(notif_list, list):
    logger.record("Notifications", "Retrieve User Notifications Feed", "PASS", f"Items count: {len(notif_list)}")
else:
    logger.record("Notifications", "Retrieve User Notifications Feed", "FAIL", str(notif_list))

# 17. User Profile & Settings
st, prof = api_call("/auth/me", token=token_a)
st_up, prof_up = api_call("/auth/profile", method="PUT", data={"full_name": "Final QA User A Senior"}, token=token_a)
if st_up == 200 and prof_up.get("full_name") == "Final QA User A Senior":
    logger.record("Profile Management", "Update Profile Name", "PASS", f"New Name: {prof_up.get('full_name')}")
else:
    logger.record("Profile Management", "Update Profile Name", "FAIL", str(prof_up))

# 18. Multi-User Isolation Verification
user_b_email = f"qa_reg_b_{ts}@expenseflow.com"
reg_b = {
    "full_name": "Final QA User B",
    "email": user_b_email,
    "password": password,
    "confirm_password": password,
    "currency": "INR"
}
st, res_b = api_call("/auth/register", method="POST", data=reg_b)
token_b = res_b["access_token"]
user_b_id = res_b["user"]["id"]

# Verify User B cannot access User A's transaction, budget, goal, or reminder
st_b_tx, _ = api_call(f"/transactions/{tx_inc1['id']}", token=token_b)
st_b_goal, _ = api_call(f"/goals/{goal_id}", token=token_b)
st_b_rem, _ = api_call(f"/reminders/{rem_id}", token=token_b)

st, b_tx_list = api_call("/transactions", token=token_b)
user_b_sees_tx = any(t["id"] == tx_inc1["id"] for t in b_tx_list.get("items", []))

if st_b_tx == 404 and st_b_goal == 404 and st_b_rem == 404 and not user_b_sees_tx:
    logger.record("Multi-User Isolation", "Cross-User Data Privacy Protection", "PASS", "User B receives 404 Not Found on all User A resources")
else:
    logger.record("Multi-User Isolation", "Cross-User Data Privacy", "FAIL", f"Tx: {st_b_tx}, Goal: {st_b_goal}, Rem: {st_b_rem}, InList: {user_b_sees_tx}")

# Log back in as User A and verify data intact
st, a_again = api_call("/auth/login", method="POST", data={"email": user_a_email, "password": password})
st_dash_a, dash_a_again = api_call("/dashboard", token=a_again["access_token"])
if st_dash_a == 200 and Decimal(str(dash_a_again["summary"]["total_balance"])) > 0:
    logger.record("Persistence & Re-login", "User A Re-login & Data Persistence", "PASS", f"Balance restored: ₹{dash_a_again['summary']['total_balance']}")
else:
    logger.record("Persistence & Re-login", "User A Re-login", "FAIL", str(dash_a_again))

print(f"\n=== REGRESSION SUITE FINISHED: {logger.passed} PASSED, {logger.failed} FAILED ===", flush=True)

# Save results to scratch
import os
os.makedirs("scratch", exist_ok=True)
with open("scratch/regression_results.json", "w") as f:
    json.dump({
        "user_a_email": user_a_email,
        "user_b_email": user_b_email,
        "password": password,
        "passed": logger.passed,
        "failed": logger.failed,
        "records": logger.records
    }, f, indent=2)
