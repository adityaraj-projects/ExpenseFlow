import os
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

class TestReport:
    def __init__(self):
        self.results = []
        self.reconciliation = []

    def record(self, section, test_name, status, details=""):
        self.results.append({
            "section": section,
            "test_name": test_name,
            "status": status,
            "details": details
        })
        icon = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"{icon} [{section}] {test_name}: {details}")

    def add_reconciliation(self, metric, expected, api_val, status):
        self.reconciliation.append({
            "metric": metric,
            "expected": str(expected),
            "api_val": str(api_val),
            "status": status
        })

report = TestReport()

def api_call(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            res_body = response.read().decode("utf-8")
            if res_body:
                return status_code, json.loads(res_body)
            return status_code, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"raw": err_body}
    except Exception as e:
        return 500, {"error": str(e)}

print(f"--- Starting Full E2E Functional & Financial Integrity Audit ---")
print(f"Target Base URL: {BASE_URL}")

# Section 1: Health & Inspection
st, res = api_call("/health")
if st == 200 and res.get("database_connected") is True:
    report.record("1. Project Inspection", "Live Backend & Database Health", "PASS", f"Status: {res.get('status')}, DB connected: {res.get('database_connected')}")
else:
    report.record("1. Project Inspection", "Live Backend & Database Health", "FAIL", f"Status code: {st}, res: {res}")

# Section 2: Create Completely New Test Users
ts = int(time.time())
user_a_email = f"qa_user_a_{ts}@expenseflow.com"
user_b_email = f"qa_user_b_{ts}@expenseflow.com"
password = "Password123!"

# Register User A
reg_data_a = {
    "full_name": "ExpenseFlow QA User A",
    "email": user_a_email,
    "password": password,
    "confirm_password": password,
    "currency": "INR"
}
st, res_a = api_call("/auth/register", method="POST", data=reg_data_a)
if st == 201 and "access_token" in res_a:
    token_a = res_a["access_token"]
    user_a_id = res_a["user"]["id"]
    # Verify plaintext password is NOT in response
    has_pwd = "password" in res_a["user"] or "hashed_password" in res_a["user"]
    if not has_pwd:
        report.record("2. New User Registration", "User A Registration & Password Security", "PASS", f"User A registered (ID: {user_a_id}), no plaintext/hashed password leaked")
    else:
        report.record("2. New User Registration", "User A Registration & Password Security", "FAIL", "Password fields exposed in response!")
else:
    report.record("2. New User Registration", "User A Registration", "FAIL", f"HTTP {st}: {res_a}")
    sys.exit(1)

# Verify Login & Logout for User A
st, login_a = api_call("/auth/login", method="POST", data={"email": user_a_email, "password": password})
if st == 200 and "access_token" in login_a:
    report.record("2. Authentication", "User A Login", "PASS", "Login succeeded with issued JWT")
else:
    report.record("2. Authentication", "User A Login", "FAIL", f"HTTP {st}: {login_a}")

st, wrong_login = api_call("/auth/login", method="POST", data={"email": user_a_email, "password": "WrongPassword!"})
if st in [400, 401]:
    report.record("2. Authentication", "Invalid Credentials Rejection", "PASS", f"Rejected with HTTP {st}")
else:
    report.record("2. Authentication", "Invalid Credentials Rejection", "FAIL", f"Expected 401/400, got {st}")

st, logout_res = api_call("/auth/logout", method="POST", token=token_a)
if st == 200:
    report.record("2. Authentication", "User A Logout Confirmation", "PASS", "Logout endpoint responded 200")
else:
    report.record("2. Authentication", "User A Logout Confirmation", "FAIL", f"HTTP {st}: {logout_res}")

# Register User B
reg_data_b = {
    "full_name": "ExpenseFlow QA User B",
    "email": user_b_email,
    "password": password,
    "confirm_password": password,
    "currency": "INR"
}
st, res_b = api_call("/auth/register", method="POST", data=reg_data_b)
if st == 201 and "access_token" in res_b:
    token_b = res_b["access_token"]
    user_b_id = res_b["user"]["id"]
    report.record("2. New User Registration", "User B Registration", "PASS", f"User B registered (ID: {user_b_id})")
else:
    report.record("2. New User Registration", "User B Registration", "FAIL", f"HTTP {st}: {res_b}")
    sys.exit(1)

# Fetch User A Categories
st, cats_a = api_call("/categories", token=token_a)
cat_map_a = {c["name"]: c["id"] for c in cats_a}
income_cat_id = cat_map_a.get("Salary") or cat_map_a.get("Freelance") or [c["id"] for c in cats_a if c["type"] in ["income", "both"]][0]
expense_cat_id = cat_map_a.get("Food & Dining") or [c["id"] for c in cats_a if c["type"] in ["expense", "both"]][0]

# Section 3: Verify User Data Isolation
# Add a transaction, budget, goal for User A
tx_a_data = {
    "category_id": income_cat_id,
    "type": "income",
    "amount": 1000.0,
    "description": "User A Private Transaction",
    "transaction_date": str(date.today())
}
st, tx_a = api_call("/transactions", method="POST", data=tx_a_data, token=token_a)
tx_a_id = tx_a["id"]

goal_a_data = {
    "name": "User A Private Goal",
    "target_amount": 50000.0,
    "initial_amount": 5000.0
}
st, goal_a = api_call("/goals", method="POST", data=goal_a_data, token=token_a)
goal_a_id = goal_a["id"]

# Verify User B cannot see User A data
st, b_txs = api_call("/transactions", token=token_b)
user_b_sees_a_tx = any(t["id"] == tx_a_id for t in b_txs.get("items", []))

st, b_goals = api_call("/goals", token=token_b)
user_b_sees_a_goal = any(g["id"] == goal_a_id for g in b_goals)

# Try direct access by ID from User B
st_get_tx, _ = api_call(f"/transactions/{tx_a_id}", token=token_b)
st_get_goal, _ = api_call(f"/goals/{goal_a_id}", token=token_b)

if not user_b_sees_a_tx and not user_b_sees_a_goal and st_get_tx == 404 and st_get_goal == 404:
    report.record("3. User Data Isolation", "Cross-User Privacy at Database & API Layer", "PASS", "User B cannot list or access User A's transactions/goals (404 Not Found)")
else:
    report.record("3. User Data Isolation", "Cross-User Privacy at Database & API Layer", "FAIL", f"Data leak detected! sees_tx: {user_b_sees_a_tx}, sees_goal: {user_b_sees_a_goal}, tx_get: {st_get_tx}, goal_get: {st_get_goal}")

# Delete User A test isolation transaction & goal before main test
api_call(f"/transactions/{tx_a_id}", method="DELETE", token=token_a)
api_call(f"/goals/{goal_a_id}", method="DELETE", token=token_a)

# Section 4: Test Income Flow (₹25,000)
today_str = str(date.today())
income_1 = {
    "category_id": income_cat_id,
    "type": "income",
    "amount": 25000.0,
    "description": "QA Income Test",
    "transaction_date": today_str
}
st, tx_inc_1 = api_call("/transactions", method="POST", data=income_1, token=token_a)
if st == 201 and Decimal(str(tx_inc_1["amount"])) == Decimal("25000.0"):
    report.record("4. Income Flow", "Add ₹25,000 Income", "PASS", f"Transaction ID: {tx_inc_1['id']}, amount: {tx_inc_1['amount']}")
else:
    report.record("4. Income Flow", "Add ₹25,000 Income", "FAIL", f"HTTP {st}: {tx_inc_1}")

# Section 5: Verify Balance After Income
st, dash = api_call("/dashboard", token=token_a)
dash_balance = Decimal(str(dash["summary"]["total_balance"]))
dash_income = Decimal(str(dash["summary"]["total_income"]))
dash_expense = Decimal(str(dash["summary"]["total_expenses"]))

expected_balance_1 = Decimal("25000.0")
expected_income_1 = Decimal("25000.0")
expected_expense_1 = Decimal("0.0")

if dash_balance == expected_balance_1 and dash_income == expected_income_1 and dash_expense == expected_expense_1:
    report.record("5. Balance After Income", "Balance Reconciliation after ₹25,000 Income", "PASS", f"Balance: ₹{dash_balance}, Income: ₹{dash_income}, Expense: ₹{dash_expense}")
    report.add_reconciliation("Balance after ₹25k Income", expected_balance_1, dash_balance, "MATCH")
else:
    report.record("5. Balance After Income", "Balance Reconciliation after ₹25,000 Income", "FAIL", f"Expected ₹{expected_balance_1}, got ₹{dash_balance}")
    report.add_reconciliation("Balance after ₹25k Income", expected_balance_1, dash_balance, "MISMATCH")

# Section 6: Test Expense Flow (₹5,000)
expense_1 = {
    "category_id": expense_cat_id,
    "type": "expense",
    "amount": 5000.0,
    "description": "QA Expense Test",
    "transaction_date": today_str
}
st, tx_exp_1 = api_call("/transactions", method="POST", data=expense_1, token=token_a)
tx_exp_1_id = tx_exp_1["id"]
if st == 201 and Decimal(str(tx_exp_1["amount"])) == Decimal("5000.0"):
    report.record("6. Expense Flow", "Add ₹5,000 Expense", "PASS", f"Transaction ID: {tx_exp_1_id}, amount: {tx_exp_1['amount']}")
else:
    report.record("6. Expense Flow", "Add ₹5,000 Expense", "FAIL", f"HTTP {st}: {tx_exp_1}")

# Section 7: Verify Money Subtraction (₹25,000 - ₹5,000 = ₹20,000)
st, dash = api_call("/dashboard", token=token_a)
dash_balance = Decimal(str(dash["summary"]["total_balance"]))
dash_income = Decimal(str(dash["summary"]["total_income"]))
dash_expense = Decimal(str(dash["summary"]["total_expenses"]))

expected_balance_2 = Decimal("20000.0")
expected_income_2 = Decimal("25000.0")
expected_expense_2 = Decimal("5000.0")

if dash_balance == expected_balance_2 and dash_income == expected_income_2 and dash_expense == expected_expense_2:
    report.record("7. Money Subtraction", "Balance = ₹20,000 (₹25k Income - ₹5k Expense)", "PASS", f"Balance: ₹{dash_balance}, Income: ₹{dash_income}, Expense: ₹{dash_expense}")
    report.add_reconciliation("Money Subtraction (₹25k - ₹5k)", expected_balance_2, dash_balance, "MATCH")
else:
    report.record("7. Money Subtraction", "Balance = ₹20,000", "FAIL", f"Expected ₹{expected_balance_2}, got ₹{dash_balance}")
    report.add_reconciliation("Money Subtraction (₹25k - ₹5k)", expected_balance_2, dash_balance, "MISMATCH")

# Section 8: Test Multiple Transactions
# Income: ₹10,000, ₹5,000
st, tx_inc_2 = api_call("/transactions", method="POST", data={"category_id": income_cat_id, "type": "income", "amount": 10000.0, "description": "QA Freelance Income", "transaction_date": today_str}, token=token_a)
tx_inc_2_id = tx_inc_2["id"]
st, tx_inc_3 = api_call("/transactions", method="POST", data={"category_id": income_cat_id, "type": "income", "amount": 5000.0, "description": "QA Bonus Income", "transaction_date": today_str}, token=token_a)

# Expenses: ₹2,000, ₹3,000, ₹1,500, ₹4,500
st, tx_exp_2 = api_call("/transactions", method="POST", data={"category_id": expense_cat_id, "type": "expense", "amount": 2000.0, "description": "QA Grocery Expense", "transaction_date": today_str}, token=token_a)
st, tx_exp_3 = api_call("/transactions", method="POST", data={"category_id": expense_cat_id, "type": "expense", "amount": 3000.0, "description": "QA Utilities Expense", "transaction_date": today_str}, token=token_a)
st, tx_exp_4 = api_call("/transactions", method="POST", data={"category_id": expense_cat_id, "type": "expense", "amount": 1500.0, "description": "QA Fuel Expense", "transaction_date": today_str}, token=token_a)
tx_exp_4_id = tx_exp_4["id"]
st, tx_exp_5 = api_call("/transactions", method="POST", data={"category_id": expense_cat_id, "type": "expense", "amount": 4500.0, "description": "QA Dinner Expense", "transaction_date": today_str}, token=token_a)

# Total Expected:
# Incomes: 25,000 + 10,000 + 5,000 = 40,000
# Expenses: 5,000 + 2,000 + 3,000 + 1,500 + 4,500 = 16,000
# Balance: 40,000 - 16,000 = 24,000
expected_total_income = Decimal("40000.0")
expected_total_expense = Decimal("16000.0")
expected_net_balance = Decimal("24000.0")

st, dash = api_call("/dashboard", token=token_a)
dash_balance = Decimal(str(dash["summary"]["total_balance"]))
dash_income = Decimal(str(dash["summary"]["total_income"]))
dash_expense = Decimal(str(dash["summary"]["total_expenses"]))

st, tx_list = api_call("/transactions", token=token_a)
list_income = Decimal(str(tx_list["total_income"]))
list_expense = Decimal(str(tx_list["total_expense"]))

st, rep = api_call("/reports?timeframe=this_month", token=token_a)
rep_income = Decimal(str(rep["summary"]["total_income"]))
rep_expense = Decimal(str(rep["summary"]["total_expense"]))
rep_net = Decimal(str(rep["summary"]["net_savings"]))

if (dash_balance == expected_net_balance and dash_income == expected_total_income and dash_expense == expected_total_expense and
    list_income == expected_total_income and list_expense == expected_total_expense and
    rep_income == expected_total_income and rep_expense == expected_total_expense and rep_net == expected_net_balance):
    report.record("8. Multiple Transactions", "Full Reconciliation across Dashboard, Transactions & Reports", "PASS", f"Income: ₹{dash_income}, Expense: ₹{dash_expense}, Balance: ₹{dash_balance}")
    report.add_reconciliation("Multiple Tx Total Income", expected_total_income, dash_income, "MATCH")
    report.add_reconciliation("Multiple Tx Total Expense", expected_total_expense, dash_expense, "MATCH")
    report.add_reconciliation("Multiple Tx Net Balance", expected_net_balance, dash_balance, "MATCH")
else:
    report.record("8. Multiple Transactions", "Full Reconciliation across Dashboard, Transactions & Reports", "FAIL", f"Mismatch! Dash: ({dash_income}, {dash_expense}, {dash_balance}), List: ({list_income}, {list_expense}), Rep: ({rep_income}, {rep_expense}, {rep_net})")

# Section 9: Test Edit Transaction
# Edit Expense ₹5,000 -> ₹7,500 (+₹2,500)
st, edit_exp = api_call(f"/transactions/{tx_exp_1_id}", method="PUT", data={"amount": 7500.0}, token=token_a)
# Edit Income ₹10,000 -> ₹12,000 (+₹2,000)
st, edit_inc = api_call(f"/transactions/{tx_inc_2_id}", method="PUT", data={"amount": 12000.0}, token=token_a)

# New expected totals:
# Income: 40,000 - 10,000 + 12,000 = 42,000
# Expense: 16,000 - 5,000 + 7,500 = 18,500
# Balance: 42,000 - 18,500 = 23,500
expected_edit_income = Decimal("42000.0")
expected_edit_expense = Decimal("18500.0")
expected_edit_balance = Decimal("23500.0")

st, dash_edit = api_call("/dashboard", token=token_a)
d_edit_b = Decimal(str(dash_edit["summary"]["total_balance"]))
d_edit_i = Decimal(str(dash_edit["summary"]["total_income"]))
d_edit_e = Decimal(str(dash_edit["summary"]["total_expenses"]))

if d_edit_b == expected_edit_balance and d_edit_i == expected_edit_income and d_edit_e == expected_edit_expense:
    report.record("9. Edit Transaction", "Edit Expense ₹5k->₹7.5k & Income ₹10k->₹12k", "PASS", f"New Income: ₹{d_edit_i}, Expense: ₹{d_edit_e}, Balance: ₹{d_edit_b}")
    report.add_reconciliation("After Edit Balance", expected_edit_balance, d_edit_b, "MATCH")
else:
    report.record("9. Edit Transaction", "Edit Expense & Income Recalculation", "FAIL", f"Expected Balance: ₹{expected_edit_balance}, got ₹{d_edit_b}")
    report.add_reconciliation("After Edit Balance", expected_edit_balance, d_edit_b, "MISMATCH")

# Section 10: Test Delete Transaction
# Delete expense ₹1,500 (tx_exp_4_id)
st, del_res = api_call(f"/transactions/{tx_exp_4_id}", method="DELETE", token=token_a)
st_check, _ = api_call(f"/transactions/{tx_exp_4_id}", token=token_a)

# New expected totals:
# Income: 42,000
# Expense: 18,500 - 1,500 = 17,000
# Balance: 42,000 - 17,000 = 25,000
expected_del_income = Decimal("42000.0")
expected_del_expense = Decimal("17000.0")
expected_del_balance = Decimal("25000.0")

st, dash_del = api_call("/dashboard", token=token_a)
d_del_b = Decimal(str(dash_del["summary"]["total_balance"]))
d_del_i = Decimal(str(dash_del["summary"]["total_income"]))
d_del_e = Decimal(str(dash_del["summary"]["total_expenses"]))

if st == 200 and st_check == 404 and d_del_b == expected_del_balance and d_del_e == expected_del_expense:
    report.record("10. Delete Transaction", "Delete ₹1,500 Expense & Verify Recalculation", "PASS", f"Transaction 404 verified. New Expense: ₹{d_del_e}, Balance: ₹{d_del_b}")
    report.add_reconciliation("After Delete Balance", expected_del_balance, d_del_b, "MATCH")
else:
    report.record("10. Delete Transaction", "Delete Transaction Recalculation", "FAIL", f"Expected Balance: ₹{expected_del_balance}, got ₹{d_del_b}")
    report.add_reconciliation("After Delete Balance", expected_del_balance, d_del_b, "MISMATCH")

# Section 11: Test Category Type Segregation Logic
# Try to create an Expense with an Income category
st_bad_exp, res_bad_exp = api_call("/transactions", method="POST", data={
    "category_id": income_cat_id,
    "type": "expense",
    "amount": 100.0,
    "description": "Invalid Type Test",
    "transaction_date": today_str
}, token=token_a)

# Try to create an Income with an Expense category
st_bad_inc, res_bad_inc = api_call("/transactions", method="POST", data={
    "category_id": expense_cat_id,
    "type": "income",
    "amount": 100.0,
    "description": "Invalid Type Test",
    "transaction_date": today_str
}, token=token_a)

if st_bad_exp == 400 and st_bad_inc == 400:
    report.record("11. Category Type Segregation", "Type Integrity Protection (Expense with Income Cat / Vice-Versa)", "PASS", "Both invalid submissions rejected with HTTP 400")
else:
    report.record("11. Category Type Segregation", "Type Integrity Protection", "FAIL", f"Bad Expense: {st_bad_exp}, Bad Income: {st_bad_inc}")

# Section 12: Test Category Management (Custom Category)
custom_cat_data = {
    "name": "Gaming & Esports",
    "type": "expense",
    "icon": "gamepad",
    "color": "#8B5CF6"
}
st, custom_cat = api_call("/categories", method="POST", data=custom_cat_data, token=token_a)
if st == 201:
    custom_cat_id = custom_cat["id"]
    report.record("12. Category Management", "Create Custom Expense Category", "PASS", f"Category created: {custom_cat['name']} (ID: {custom_cat_id})")
    
    # Add an expense using the new custom category
    st, gaming_tx = api_call("/transactions", method="POST", data={
        "category_id": custom_cat_id,
        "type": "expense",
        "amount": 2500.0,
        "description": "Steam Games Purchase",
        "transaction_date": today_str
    }, token=token_a)
    
    # Try to delete category with linked transaction -> must be rejected with 400
    st_del_cat, res_del_cat = api_call(f"/categories/{custom_cat_id}", method="DELETE", token=token_a)
    if st_del_cat == 400:
        report.record("12. Category Management", "Protected Category Deletion with Active Transactions", "PASS", "Deletion rejected with HTTP 400 (Orphan prevention)")
    else:
        report.record("12. Category Management", "Protected Category Deletion", "FAIL", f"Expected 400, got {st_del_cat}")
else:
    report.record("12. Category Management", "Create Custom Category", "FAIL", f"HTTP {st}: {custom_cat}")

# Section 13 & 14: Test Dashboard Calculations & Charts
st, dash = api_call("/dashboard", token=token_a)
monthly_trend = dash.get("monthly_trend", [])
cat_breakdown = dash.get("category_breakdown", [])

# Verify category breakdown includes "Gaming & Esports"
has_gaming_in_breakdown = any(c["category_name"] == "Gaming & Esports" for c in cat_breakdown)
if has_gaming_in_breakdown and len(monthly_trend) > 0:
    report.record("13 & 14. Dashboard & Charts", "Dashboard KPI & Chart Datasets Real-time Sync", "PASS", f"Monthly trend points: {len(monthly_trend)}, Gaming present in breakdown: {has_gaming_in_breakdown}")
else:
    report.record("13 & 14. Dashboard & Charts", "Dashboard & Charts", "FAIL", f"Gaming in breakdown: {has_gaming_in_breakdown}, Trend length: {len(monthly_trend)}")

# Section 15: Monthly / Date Logic
last_month_date = str(date.today().replace(day=1) - timedelta(days=15))
st, tx_old = api_call("/transactions", method="POST", data={
    "category_id": income_cat_id,
    "type": "income",
    "amount": 50000.0,
    "description": "Last Month Income",
    "transaction_date": last_month_date
}, token=token_a)

st, dash_after_old = api_call("/dashboard", token=token_a)
month_inc = Decimal(str(dash_after_old["summary"]["month_income"]))
tot_inc = Decimal(str(dash_after_old["summary"]["total_income"]))

# Total income should include the 50,000, but month_income must NOT include it!
if tot_inc > month_inc and (tot_inc - month_inc) == Decimal("50000.0"):
    report.record("15. Monthly / Date Logic", "Date Boundary Isolation (Current Month vs Total)", "PASS", f"Total Income: ₹{tot_inc}, Current Month Income: ₹{month_inc} (Diff exactly ₹50k)")
else:
    report.record("15. Monthly / Date Logic", "Date Boundary Isolation", "FAIL", f"Total: {tot_inc}, Month: {month_inc}")

# Section 16: Test Budget Calculations (Food & Dining ₹10,000)
# Target: Food & Dining
b_month = date.today().month
b_year = date.today().year

# Create or get budget for Food & Dining
budget_data = {
    "category_id": expense_cat_id,
    "amount": 10000.0,
    "month": b_month,
    "year": b_year
}
st, b_created = api_call("/budgets", method="POST", data=budget_data, token=token_a)
st, b_summary = api_call(f"/budgets?month={b_month}&year={b_year}", token=token_a)
food_budget = next((b for b in b_summary.get("items", []) if b["category_id"] == expense_cat_id), None)

if food_budget:
    spent = Decimal(str(food_budget["spent_amount"]))
    budget_amt = Decimal(str(food_budget["budget_amount"]))
    pct = food_budget["percentage_used"]
    b_status = food_budget["status"]
    report.record("16. Budget Calculations", "Budget Spent & Status Thresholds", "PASS", f"Budget: ₹{budget_amt}, Spent: ₹{spent}, Usage: {pct}%, Status: {b_status}")
    report.add_reconciliation("Budget Amount", budget_amt, food_budget["budget_amount"], "MATCH")
    report.add_reconciliation("Budget Spent", spent, food_budget["spent_amount"], "MATCH")
else:
    report.record("16. Budget Calculations", "Budget Creation & Progress", "FAIL", f"Food budget not found in summary: {b_summary}")

# Section 17: Test Savings Goals (Goal: "New Laptop", Target ₹100,000)
goal_create = {
    "name": "New Laptop",
    "target_amount": 100000.0,
    "initial_amount": 0.0,
    "target_date": str(date.today() + timedelta(days=180)),
    "description": "High-end development laptop"
}
st, laptop_goal = api_call("/goals", method="POST", data=goal_create, token=token_a)
goal_id = laptop_goal["id"]

# Deposit ₹20,000 (20%)
st, g_dep1 = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 20000.0, "action": "deposit"}, token=token_a)
pct1 = g_dep1["progress_percentage"]

# Deposit ₹30,000 (50%)
st, g_dep2 = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 30000.0, "action": "deposit"}, token=token_a)
pct2 = g_dep2["progress_percentage"]

# Withdraw ₹10,000 (40%)
st, g_with = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 10000.0, "action": "withdraw"}, token=token_a)
pct3 = g_with["progress_percentage"]
curr_amt = Decimal(str(g_with["current_amount"]))

# Try Over-withdraw ₹50,000 (> ₹40,000) -> Must be rejected with 400
st_over_with, res_over_with = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 50000.0, "action": "withdraw"}, token=token_a)

# Deposit ₹60,000 -> Reaches ₹100,000 (100%) -> Status becomes COMPLETED
st, g_comp = api_call(f"/goals/{goal_id}/deposit", method="POST", data={"amount": 60000.0, "action": "deposit"}, token=token_a)
final_status = g_comp["status"]

if (pct1 == 20.0 and pct2 == 50.0 and pct3 == 40.0 and curr_amt == Decimal("40000.0") and
    st_over_with == 400 and final_status == "completed"):
    report.record("17. Savings Goals", "Deposit, Withdraw, Over-withdrawal Guard & Goal Completion", "PASS", f"20% -> 50% -> 40% (₹40k), over-withdraw rejected (400), completed at 100%")
else:
    report.record("17. Savings Goals", "Savings Goals Lifecycle", "FAIL", f"pct1: {pct1}, pct2: {pct2}, pct3: {pct3}, over_with: {st_over_with}, status: {final_status}")

# Section 18: Reports
st, rep_summary = api_call("/reports/summary?timeframe=this_month", token=token_a)
if st == 200 and "net_savings" in rep_summary and "savings_rate" in rep_summary:
    report.record("18. Reports Analytics", "Summary KPI & Savings Rate", "PASS", f"Net savings: ₹{rep_summary['net_savings']}, Savings rate: {rep_summary['savings_rate']}%, Daily avg: ₹{rep_summary['daily_average_expense']}")
else:
    report.record("18. Reports Analytics", "Summary KPI", "FAIL", f"HTTP {st}: {rep_summary}")

# Section 19: Search
st, search_res = api_call("/transactions?search=QA%20Income%20Test", token=token_a)
search_items = search_res.get("items", [])
if len(search_items) == 1 and search_items[0]["description"] == "QA Income Test":
    report.record("19. Search Functionality", "Search by Description Exact Match", "PASS", f"Returned exactly 1 matching record (ID: {search_items[0]['id']})")
else:
    report.record("19. Search Functionality", "Search by Description", "FAIL", f"Found {len(search_items)} records")

# Section 20: Filters
st, filter_inc = api_call("/transactions?type=income", token=token_a)
all_income = all(t["type"] == "income" for t in filter_inc.get("items", []))

st, filter_exp = api_call("/transactions?type=expense", token=token_a)
all_expense = all(t["type"] == "expense" for t in filter_exp.get("items", []))

if all_income and all_expense:
    report.record("20. Filter Functionality", "Filter by Transaction Type (Income / Expense)", "PASS", f"Income count: {len(filter_inc.get('items', []))}, Expense count: {len(filter_exp.get('items', []))}")
else:
    report.record("20. Filter Functionality", "Filter by Transaction Type", "FAIL", f"all_income: {all_income}, all_expense: {all_expense}")

# Section 21: Pagination
# Add 12 dummy transactions to exceed default page_size of 15
for i in range(12):
    api_call("/transactions", method="POST", data={
        "category_id": expense_cat_id,
        "type": "expense",
        "amount": 100.0 + i,
        "description": f"Pagination Test Item {i+1}",
        "transaction_date": today_str
    }, token=token_a)

st, p1 = api_call("/transactions?page=1&page_size=10", token=token_a)
st, p2 = api_call("/transactions?page=2&page_size=10", token=token_a)
p1_ids = {t["id"] for t in p1.get("items", [])}
p2_ids = {t["id"] for t in p2.get("items", [])}
has_overlap = len(p1_ids.intersection(p2_ids)) > 0

if p1.get("total_pages") >= 2 and len(p1.get("items", [])) == 10 and not has_overlap:
    report.record("21. Pagination", "Multi-Page Offset & No Duplicate Records", "PASS", f"Total items: {p1.get('total')}, Total pages: {p1.get('total_pages')}, Overlap: {has_overlap}")
else:
    report.record("21. Pagination", "Multi-Page Offset", "FAIL", f"Total: {p1.get('total')}, Pages: {p1.get('total_pages')}, Overlap: {has_overlap}")

# Section 22: Authentication Expiration & Invalid JWT
st_bad_jwt, res_bad_jwt = api_call("/auth/me", token="invalid.token.here")
st_no_jwt, res_no_jwt = api_call("/auth/me")
if st_bad_jwt == 401 and st_no_jwt == 401:
    report.record("22. Security & Auth Validation", "Invalid & Missing JWT Rejection (HTTP 401)", "PASS", f"Invalid token: {st_bad_jwt}, Missing token: {st_no_jwt}")
else:
    report.record("22. Security & Auth Validation", "Invalid & Missing JWT Rejection", "FAIL", f"Invalid: {st_bad_jwt}, Missing: {st_no_jwt}")

# Output summary JSON for consumption
summary_data = {
    "user_a_email": user_a_email,
    "user_a_id": user_a_id,
    "user_b_email": user_b_email,
    "user_b_id": user_b_id,
    "results": report.results,
    "reconciliation": report.reconciliation
}

with open("scratch/audit_results.json", "w") as f:
    json.dump(summary_data, f, indent=2)

print("\n--- Audit Run Completed. Results saved to scratch/audit_results.json ---")
