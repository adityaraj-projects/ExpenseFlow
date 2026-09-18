"""
Comprehensive Automated QA Test Suite for ExpenseFlow
Tests Authentication, CRUD, Data Isolation, Calculations, and Database Integrity.
"""
import httpx as requests
import pymysql
import os
import sys
from datetime import datetime, date

BASE_URL = os.environ.get("TEST_API_URL", "http://127.0.0.1:8000/api")
DB_CONFIG = {
    "host": os.environ.get("TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TEST_DB_PORT", "3306")),
    "user": os.environ.get("TEST_DB_USER", "root"),
    "password": os.environ.get("TEST_DB_PASS", ""),
    "database": os.environ.get("TEST_DB_NAME", "expense_flow")
}

def get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.DictCursor
    )

def run_all_qa_tests():
    print("=" * 60)
    print("STARTING EXPENSEFLOW AUTOMATED QA SUITE")
    print("=" * 60)
    
    passed_count = 0
    failed_count = 0
    failures = []

    def assert_test(condition, name, details=""):
        nonlocal passed_count, failed_count
        if condition:
            passed_count += 1
            print(f"  [PASS] {name}")
        else:
            failed_count += 1
            print(f"  [FAIL] {name}: {details}")
            failures.append((name, details))

    # ---------------------------------------------------------
    # 1. DATABASE CONNECTIVITY & SCHEMA INTEGRITY
    # ---------------------------------------------------------
    print("\n--- 1. DATABASE & SCHEMA CHECKS ---")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            required_tables = [
                "users", "categories", "transactions", "budgets", "savings_goals",
                "reminders", "recurring_transactions", "notifications", "push_subscriptions", "user_preferences"
            ]
            for t in required_tables:
                assert_test(t in tables, f"Table '{t}' exists in MySQL")

            # Check foreign keys on transactions table
            cursor.execute("""
                SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, DELETE_RULE
                FROM information_schema.REFERENTIAL_CONSTRAINTS
                WHERE CONSTRAINT_SCHEMA = 'expense_flow' AND TABLE_NAME = 'transactions'
            """)
            fks = {row["REFERENCED_TABLE_NAME"]: row["DELETE_RULE"] for row in cursor.fetchall()}
            assert_test("users" in fks, "Foreign key from transactions to users exists")
            assert_test("categories" in fks, "Foreign key from transactions to categories exists")
            assert_test("recurring_transactions" in fks, "Foreign key from transactions to recurring_transactions exists")
    finally:
        conn.close()

    # ---------------------------------------------------------
    # 2. AUTHENTICATION & JWT SECURITY
    # ---------------------------------------------------------
    print("\n--- 2. AUTHENTICATION & SECURITY ---")
    ts = int(datetime.now().timestamp())
    email_a = f"qa_user_a_{ts}@expenseflow.com"
    pwd_a = "SecretPass123!"
    
    # 2.1 Register User A
    reg_res = requests.post(f"{BASE_URL}/auth/register", json={
        "full_name": "QA User Alpha",
        "email": email_a,
        "password": pwd_a,
        "confirm_password": pwd_a,
        "currency": "INR"
    })
    assert_test(reg_res.status_code == 201, "User A Registration Returns 201", reg_res.text)
    user_a_data = reg_res.json()
    assert_test("access_token" in user_a_data, "Registration returns JWT access token")
    token_a = user_a_data.get("access_token")
    user_a_id = user_a_data.get("user", {}).get("id")

    # 2.2 Verify User A in MySQL directly
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email_a,))
            db_user_a = cursor.fetchone()
            assert_test(db_user_a is not None, "User A actually persisted in MySQL")
            assert_test(db_user_a["password_hash"] != pwd_a, "User password is strongly hashed in MySQL")
            assert_test(db_user_a["password_hash"].startswith("$2b$") or db_user_a["password_hash"].startswith("$2a$"), "Password uses bcrypt hash")
            assert_test("password" not in user_a_data["user"] and "password_hash" not in user_a_data["user"], "API does NOT leak password_hash in response")
    finally:
        conn.close()

    # 2.3 Verify /api/auth/me with Valid Token
    headers_a = {"Authorization": f"Bearer {token_a}"}
    me_res = requests.get(f"{BASE_URL}/auth/me", headers=headers_a)
    assert_test(me_res.status_code == 200, "GET /api/auth/me with valid JWT returns 200")
    assert_test(me_res.json().get("email") == email_a, "/api/auth/me returns correct user data")

    # 2.4 Verify Invalid / Expired / Missing JWT Handling
    no_jwt_res = requests.get(f"{BASE_URL}/auth/me")
    assert_test(no_jwt_res.status_code == 401, "GET /api/auth/me without JWT returns 401")

    bad_jwt_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert_test(bad_jwt_res.status_code == 401, "GET /api/auth/me with invalid JWT returns 401")

    # 2.5 Login with Invalid Credentials
    bad_login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email_a,
        "password": "WrongPassword!"
    })
    assert_test(bad_login_res.status_code == 401, "Login with wrong password returns 401")

    # 2.6 Login with Valid Credentials
    login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email_a,
        "password": pwd_a
    })
    assert_test(login_res.status_code == 200, "Login with valid credentials returns 200")
    assert_test("access_token" in login_res.json(), "Login returns new JWT access token")

    # ---------------------------------------------------------
    # 3. CATEGORIES CRUD & INTEGRITY
    # ---------------------------------------------------------
    print("\n--- 3. CATEGORIES CRUD & CONSTRAINTS ---")
    # 3.1 Get categories (system seeded + user default)
    cats_res = requests.get(f"{BASE_URL}/categories", headers=headers_a)
    assert_test(cats_res.status_code == 200, "GET /api/categories returns 200")
    cats_a = cats_res.json()
    assert_test(len(cats_a) > 0, "Default system/seeded categories available to new user")
    food_cat = next((c for c in cats_a if "food" in c["name"].lower() or "dining" in c["name"].lower()), cats_a[0])
    salary_cat = next((c for c in cats_a if "salary" in c["name"].lower() or "income" in c["name"].lower()), cats_a[-1])

    # 3.2 Create custom category for User A
    create_cat_res = requests.post(f"{BASE_URL}/categories", headers=headers_a, json={
        "name": f"Freelance QA {ts}",
        "type": "income",
        "color": "#10B981",
        "icon": "briefcase"
    })
    assert_test(create_cat_res.status_code == 201, "Create custom category returns 201")
    custom_cat = create_cat_res.json()
    custom_cat_id = custom_cat["id"]

    # 3.3 Edit custom category
    edit_cat_res = requests.put(f"{BASE_URL}/categories/{custom_cat_id}", headers=headers_a, json={
        "name": f"Freelance Consulting {ts}",
        "color": "#059669"
    })
    assert_test(edit_cat_res.status_code == 200, "Edit custom category returns 200")

    # ---------------------------------------------------------
    # 4. TRANSACTIONS CRUD & CALCULATIONS
    # ---------------------------------------------------------
    print("\n--- 4. TRANSACTIONS CRUD & DASHBOARD/REPORT SYNC ---")
    today_str = date.today().isoformat()
    
    # 4.1 Create Income Transaction
    tx_inc_res = requests.post(f"{BASE_URL}/transactions", headers=headers_a, json={
        "category_id": custom_cat_id,
        "amount": 50000.00,
        "type": "income",
        "transaction_date": today_str,
        "description": "Consulting retainer fee",
        "payment_method": "bank_transfer"
    })
    assert_test(tx_inc_res.status_code == 201, "Create Income Transaction returns 201")
    tx_inc = tx_inc_res.json()
    tx_inc_id = tx_inc["id"]

    # 4.2 Create Expense Transaction
    tx_exp_res = requests.post(f"{BASE_URL}/transactions", headers=headers_a, json={
        "category_id": food_cat["id"],
        "amount": 2500.00,
        "type": "expense",
        "transaction_date": today_str,
        "description": "Team lunch buffet",
        "payment_method": "credit_card"
    })
    assert_test(tx_exp_res.status_code == 201, "Create Expense Transaction returns 201")
    tx_exp = tx_exp_res.json()
    tx_exp_id = tx_exp["id"]

    # 4.3 Verify Attempt to Delete Category Linked to Transaction
    del_linked_cat = requests.delete(f"{BASE_URL}/categories/{custom_cat_id}", headers=headers_a)
    assert_test(del_linked_cat.status_code in [400, 409], "Cannot delete category linked to active transactions (returns 400/409)")

    # 4.4 Verify Dashboard totals match MySQL
    dash_res = requests.get(f"{BASE_URL}/dashboard", headers=headers_a)
    assert_test(dash_res.status_code == 200, "GET /api/dashboard returns 200")
    dash_data = dash_res.json()
    summary = dash_data["summary"]
    assert_test(float(summary["month_income"]) == 50000.00, "Dashboard month_income matches transactions exactly")
    assert_test(float(summary["month_expense"]) == 2500.00, "Dashboard month_expense matches transactions exactly")
    assert_test(float(summary["total_balance"]) == 47500.00, "Dashboard total_balance matches income - expense")

    # 4.5 Edit Expense Transaction
    edit_exp_res = requests.put(f"{BASE_URL}/transactions/{tx_exp_id}", headers=headers_a, json={
        "amount": 3000.00,
        "description": "Team lunch & dessert buffet"
    })
    assert_test(edit_exp_res.status_code == 200, "Edit Expense Transaction returns 200")

    # Verify Dashboard updated after edit
    dash_res2 = requests.get(f"{BASE_URL}/dashboard", headers=headers_a)
    assert_test(float(dash_res2.json()["summary"]["month_expense"]) == 3000.00, "Dashboard month_expense dynamically reflects edit")

    # 4.6 Search & Filter Transactions
    search_res = requests.get(f"{BASE_URL}/transactions", headers=headers_a, params={"search": "dessert"})
    assert_test(search_res.status_code == 200, "Search transactions returns 200")
    assert_test(len(search_res.json()["items"]) == 1, "Search returns exactly 1 matching record")

    filter_type_res = requests.get(f"{BASE_URL}/transactions", headers=headers_a, params={"type": "income"})
    assert_test(filter_type_res.status_code == 200, "Filter by type=income returns 200")
    assert_test(all(t["type"] == "income" for t in filter_type_res.json()["items"]), "All returned items are income")

    # 4.7 Pagination
    page_res = requests.get(f"{BASE_URL}/transactions", headers=headers_a, params={"page": 1, "page_size": 1})
    assert_test(page_res.status_code == 200, "Pagination request returns 200")
    assert_test(len(page_res.json()["items"]) == 1, "Page size limit of 1 respected")
    assert_test(page_res.json()["total"] == 2, "Total item count is 2")

    # ---------------------------------------------------------
    # 5. USER DATA ISOLATION (CRITICAL SECURITY)
    # ---------------------------------------------------------
    print("\n--- 5. USER DATA ISOLATION ---")
    email_b = f"qa_user_b_{ts}@expenseflow.com"
    pwd_b = "SecretPass456!"
    reg_b_res = requests.post(f"{BASE_URL}/auth/register", json={
        "full_name": "QA User Beta",
        "email": email_b,
        "password": pwd_b,
        "confirm_password": pwd_b,
        "currency": "INR"
    })
    assert_test(reg_b_res.status_code == 201, "User B Registration Returns 201")
    token_b = reg_b_res.json().get("access_token")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B creates an expense
    b_cat = requests.get(f"{BASE_URL}/categories", headers=headers_b).json()[0]
    tx_b_res = requests.post(f"{BASE_URL}/transactions", headers=headers_b, json={
        "category_id": b_cat["id"],
        "amount": 9999.00,
        "type": "expense",
        "transaction_date": today_str,
        "description": "User B Confidential Purchase"
    })
    tx_b_id = tx_b_res.json()["id"]

    # User A tries to access User B's transaction
    leak_get = requests.get(f"{BASE_URL}/transactions/{tx_b_id}", headers=headers_a)
    assert_test(leak_get.status_code in [403, 404], "User A cannot GET User B's transaction (returns 403 or 404)")

    leak_put = requests.put(f"{BASE_URL}/transactions/{tx_b_id}", headers=headers_a, json={"amount": 1.00})
    assert_test(leak_put.status_code in [403, 404], "User A cannot PUT User B's transaction (returns 403 or 404)")

    leak_del = requests.delete(f"{BASE_URL}/transactions/{tx_b_id}", headers=headers_a)
    assert_test(leak_del.status_code in [403, 404], "User A cannot DELETE User B's transaction (returns 403 or 404)")

    # User A transactions list must NOT contain User B's transaction
    tx_list_a = requests.get(f"{BASE_URL}/transactions", headers=headers_a).json()["items"]
    assert_test(all(t["id"] != tx_b_id for t in tx_list_a), "User A transactions list does NOT contain User B records")

    # ---------------------------------------------------------
    # 6. BUDGETS: CRUD, DUPLICATE PREVENTION, STATUS CALCULATIONS
    # ---------------------------------------------------------
    print("\n--- 6. BUDGETS: CRUD & STATUS CALCULATIONS ---")
    current_month = date.today().month
    current_year = date.today().year

    # 6.1 Create Budget for food category (Spent so far is 3000.00)
    # Set limit to 10000 -> 30% spent -> 'safe'
    bgt_res = requests.post(f"{BASE_URL}/budgets", headers=headers_a, json={
        "category_id": food_cat["id"],
        "amount": 10000.00,
        "month": current_month,
        "year": current_year
    })
    assert_test(bgt_res.status_code == 201, "Create Budget returns 201")
    bgt_id = bgt_res.json()["id"]

    # 6.2 Duplicate Budget Prevention
    dup_bgt_res = requests.post(f"{BASE_URL}/budgets", headers=headers_a, json={
        "category_id": food_cat["id"],
        "amount": 12000.00,
        "month": current_month,
        "year": current_year
    })
    assert_test(dup_bgt_res.status_code in [400, 409], "Duplicate budget for same category/month/year rejected (400/409)")

    # 6.3 Verify Budget Calculations & Status 'safe'
    bgts_list = requests.get(f"{BASE_URL}/budgets", headers=headers_a, params={"month": current_month, "year": current_year}).json()
    bgt_item = next((b for b in bgts_list["items"] if b["id"] == bgt_id), None)
    assert_test(bgt_item is not None, "Budget appears in monthly budgets list")
    assert_test(float(bgt_item["spent_amount"]) == 3000.00, "Budget spent_amount correctly calculates 3000.00 from transactions")
    assert_test(float(bgt_item["remaining_amount"]) == 7000.00, "Budget remaining_amount correctly calculates 7000.00")
    assert_test(bgt_item["percentage_used"] == 30.0, "Budget percentage_used is exactly 30.0%")
    assert_test(bgt_item["status"] == "safe", "Budget status is 'safe' (<80%)")

    # 6.4 Edit Budget to test 'warning' state (Limit 3500 -> Spent 3000 -> 85.7% -> 'warning')
    edit_bgt_res = requests.put(f"{BASE_URL}/budgets/{bgt_id}", headers=headers_a, json={
        "amount": 3500.00
    })
    assert_test(edit_bgt_res.status_code == 200, "Edit Budget returns 200")
    bgt_warn = requests.get(f"{BASE_URL}/budgets", headers=headers_a, params={"month": current_month, "year": current_year}).json()["items"][0]
    assert_test(bgt_warn["status"] == "warning", "Budget status transitions to 'warning' (>=80% and <=100%)")

    # 6.5 Edit Budget to test 'exceeded' state (Limit 2000 -> Spent 3000 -> 150% -> 'exceeded')
    requests.put(f"{BASE_URL}/budgets/{bgt_id}", headers=headers_a, json={"amount": 2000.00})
    bgt_exceed = requests.get(f"{BASE_URL}/budgets", headers=headers_a, params={"month": current_month, "year": current_year}).json()["items"][0]
    assert_test(bgt_exceed["status"] == "exceeded", "Budget status transitions to 'exceeded' (>100%)")
    assert_test(float(bgt_exceed["remaining_amount"]) == -1000.00, "Budget remaining_amount is negative (-1000.00) when exceeded")

    # 6.6 Isolation on Budgets: User B cannot view or edit User A's budget
    b_bgt_leak = requests.get(f"{BASE_URL}/budgets/{bgt_id}", headers=headers_b)
    assert_test(b_bgt_leak.status_code in [403, 404], "User B cannot GET User A's budget")
    b_bgt_edit = requests.put(f"{BASE_URL}/budgets/{bgt_id}", headers=headers_b, json={"amount": 9999.00})
    assert_test(b_bgt_edit.status_code in [403, 404], "User B cannot PUT User A's budget")

    # ---------------------------------------------------------
    # 7. SAVINGS GOALS: CRUD, DEPOSITS, WITHDRAWALS & COMPLETION
    # ---------------------------------------------------------
    print("\n--- 7. SAVINGS GOALS: CRUD & FUNDS OPERATIONS ---")
    # 7.1 Create Savings Goal
    goal_res = requests.post(f"{BASE_URL}/goals", headers=headers_a, json={
        "name": "New Laptop",
        "target_amount": 100000.00,
        "initial_amount": 10000.00,
        "target_date": "2026-12-31"
    })
    assert_test(goal_res.status_code == 201, "Create Savings Goal returns 201")
    goal = goal_res.json()
    goal_id = goal["id"]
    assert_test(float(goal["current_amount"]) == 10000.00, "Initial deposit applied correctly")
    assert_test(goal["status"] == "in_progress", "Goal status is 'in_progress'")

    # 7.2 Deposit Funds into Goal
    dep_res = requests.post(f"{BASE_URL}/goals/{goal_id}/deposit", headers=headers_a, json={
        "amount": 40000.00,
        "action": "deposit"
    })
    assert_test(dep_res.status_code == 200, "Deposit funds into goal returns 200")
    goal_after_dep = dep_res.json()
    assert_test(float(goal_after_dep["current_amount"]) == 50000.00, "Current amount is 50000.00 after deposit")
    assert_test(goal_after_dep["progress_percentage"] == 50.0, "Progress percentage is 50.0%")

    # 7.3 Withdraw Funds from Goal
    with_res = requests.post(f"{BASE_URL}/goals/{goal_id}/deposit", headers=headers_a, json={
        "amount": 5000.00,
        "action": "withdraw"
    })
    assert_test(with_res.status_code == 200, "Withdraw funds from goal returns 200")
    assert_test(float(with_res.json()["current_amount"]) == 45000.00, "Current amount is 45000.00 after withdrawal")

    # 7.4 Attempt Over-withdrawal (withdraw 50000 from 45000)
    over_res = requests.post(f"{BASE_URL}/goals/{goal_id}/deposit", headers=headers_a, json={
        "amount": 50000.00,
        "action": "withdraw"
    })
    assert_test(over_res.status_code == 400, "Over-withdrawal is rejected with 400 Bad Request")

    # 7.5 Complete Goal (Deposit remaining 55000)
    comp_res = requests.post(f"{BASE_URL}/goals/{goal_id}/deposit", headers=headers_a, json={
        "amount": 55000.00,
        "action": "deposit"
    })
    assert_test(comp_res.status_code == 200, "Deposit to complete goal returns 200")
    goal_comp = comp_res.json()
    assert_test(float(goal_comp["current_amount"]) == 100000.00, "Goal reached target 100000.00")
    assert_test(goal_comp["status"] == "completed", "Goal status transitioned to 'completed'")

    # 7.6 Isolation on Goals: User B cannot access User A's goal
    b_goal_leak = requests.get(f"{BASE_URL}/goals/{goal_id}", headers=headers_b)
    assert_test(b_goal_leak.status_code in [403, 404], "User B cannot GET User A's goal")

    # ---------------------------------------------------------
    # 8. REPORTS: TIMEFRAMES, LABELS, EXACT_DATES & CALCULATIONS
    # ---------------------------------------------------------
    print("\n--- 8. REPORTS: TIMEFRAMES, CHART LABELS & TOOLTIPS ---")
    timeframes = ["this_week", "this_month", "last_month", "this_year"]
    for tf in timeframes:
        rep = requests.get(f"{BASE_URL}/reports", headers=headers_a, params={"timeframe": tf})
        assert_test(rep.status_code == 200, f"Reports API for timeframe '{tf}' returns 200")
        data = rep.json()
        assert_test("summary" in data and "time_series" in data and "expense_categories" in data, f"Report structure complete for '{tf}'")
        
        # Verify exact_date and label readability
        series = data["time_series"]
        if series:
            first_item = series[0]
            assert_test("date_label" in first_item, f"Series items contain 'date_label' ({tf})")
            assert_test("exact_date" in first_item and first_item["exact_date"] is not None, f"Series items contain rich 'exact_date' ({tf})")
            labels = [item["date_label"] for item in series]
            # Check for no duplicate adjacent labels
            adjacent_dups = [labels[i] for i in range(len(labels)-1) if labels[i] == labels[i+1]]
            assert_test(len(adjacent_dups) == 0, f"No adjacent duplicate labels in '{tf}' chart series")

    # ---------------------------------------------------------
    # 9. API ERROR HANDLING & EDGE CASES
    # ---------------------------------------------------------
    print("\n--- 9. API ERROR RESPONSES & VALIDATION ---")
    # Invalid transaction ID
    bad_tx_id = requests.get(f"{BASE_URL}/transactions/9999999", headers=headers_a)
    assert_test(bad_tx_id.status_code == 404, "GET non-existent transaction returns 404")

    # Invalid category ID in transaction
    bad_cat_tx = requests.post(f"{BASE_URL}/transactions", headers=headers_a, json={
        "category_id": 9999999,
        "amount": 100.0,
        "type": "expense",
        "transaction_date": today_str,
        "description": "Test"
    })
    assert_test(bad_cat_tx.status_code in [400, 404], "Transaction with non-existent category returns 400 or 404")

    # Negative amount validation
    neg_amt = requests.post(f"{BASE_URL}/transactions", headers=headers_a, json={
        "category_id": food_cat["id"],
        "amount": -50.0,
        "type": "expense",
        "transaction_date": today_str,
        "description": "Negative amount test"
    })
    assert_test(neg_amt.status_code in [400, 422], "Negative transaction amount rejected (400/422)")

    # ---------------------------------------------------------
    # 10. DATABASE INTEGRITY & ORPHAN RECORD VERIFICATION
    # ---------------------------------------------------------
    print("\n--- 10. DATABASE ORPHAN RECORDS & RELATIONAL INTEGRITY ---")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check orphan transactions (transactions with user_id not in users)
            cursor.execute("SELECT COUNT(*) AS c FROM transactions WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_tx = cursor.fetchone()["c"]
            assert_test(orphan_tx == 0, "No orphan transactions in MySQL")

            # Check orphan budgets
            cursor.execute("SELECT COUNT(*) AS c FROM budgets WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_bgt = cursor.fetchone()["c"]
            assert_test(orphan_bgt == 0, "No orphan budgets in MySQL")

            # Check orphan goals
            cursor.execute("SELECT COUNT(*) AS c FROM savings_goals WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_goals = cursor.fetchone()["c"]
            assert_test(orphan_goals == 0, "No orphan savings goals in MySQL")

            # Check orphan reminders
            cursor.execute("SELECT COUNT(*) AS c FROM reminders WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_rem = cursor.fetchone()["c"]
            assert_test(orphan_rem == 0, "No orphan reminders in MySQL")

            # Check orphan recurring transactions
            cursor.execute("SELECT COUNT(*) AS c FROM recurring_transactions WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_rec = cursor.fetchone()["c"]
            assert_test(orphan_rec == 0, "No orphan recurring transactions in MySQL")

            # Check orphan notifications
            cursor.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_notifs = cursor.fetchone()["c"]
            assert_test(orphan_notifs == 0, "No orphan notifications in MySQL")

            # Check orphan push subscriptions
            cursor.execute("SELECT COUNT(*) AS c FROM push_subscriptions WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_push = cursor.fetchone()["c"]
            assert_test(orphan_push == 0, "No orphan push subscriptions in MySQL")

            # Check orphan user preferences
            cursor.execute("SELECT COUNT(*) AS c FROM user_preferences WHERE user_id NOT IN (SELECT id FROM users)")
            orphan_pref = cursor.fetchone()["c"]
            assert_test(orphan_pref == 0, "No orphan user preferences in MySQL")
    finally:
        conn.close()

    # ---------------------------------------------------------
    # 11. REMINDERS CRUD, CALENDAR RECURRENCE, SNOOZE & COMPLETION
    # ---------------------------------------------------------
    print("\n--- 11. REMINDERS SYSTEM & RECURRENCE ---")
    # 11.1 Create one-time reminder
    rem_res1 = requests.post(f"{BASE_URL}/reminders", headers=headers_a, json={
        "title": "Electricity Bill Payment",
        "description": "Pay before 8pm",
        "amount": 1250.0,
        "reminder_date": today_str,
        "recurrence": "once",
        "category_id": food_cat["id"]
    })
    assert_test(rem_res1.status_code == 201, "User A creates one-time reminder (201)", rem_res1.text)
    rem1 = rem_res1.json()
    assert_test(rem1.get("status") == "pending", "Initial reminder status is pending")
    rem1_id = rem1.get("id")

    # 11.2 Snooze reminder (+3 days)
    snooze_res = requests.patch(f"{BASE_URL}/reminders/{rem1_id}/snooze", headers=headers_a, json={"days": 3})
    assert_test(snooze_res.status_code == 200, "User A snoozes reminder (200)", snooze_res.text)
    snoozed_rem = snooze_res.json()
    assert_test(snoozed_rem.get("status") == "snoozed", "Reminder status updated to snoozed")

    # 11.3 Mark completed
    comp_res = requests.patch(f"{BASE_URL}/reminders/{rem1_id}/complete", headers=headers_a)
    assert_test(comp_res.status_code == 200, "User A completes reminder (200)", comp_res.text)
    comp_rem = comp_res.json()
    assert_test(comp_rem.get("status") == "completed", "Reminder status updated to completed")

    # 11.4 User B cannot access or complete User A's reminder
    b_rem_res = requests.get(f"{BASE_URL}/reminders/{rem1_id}", headers=headers_b)
    assert_test(b_rem_res.status_code == 404, "User B cannot view User A's reminder (404 isolation)")

    # 11.5 Recurring reminder creation & calendar-safe recurrence check
    rem_res2 = requests.post(f"{BASE_URL}/reminders", headers=headers_a, json={
        "title": "Monthly Wifi Broadband",
        "amount": 999.0,
        "reminder_date": today_str,
        "recurrence": "monthly",
        "category_id": food_cat["id"]
    })
    assert_test(rem_res2.status_code == 201, "User A creates monthly recurring reminder (201)")
    rem2 = rem_res2.json()
    assert_test(rem2.get("recurrence") == "monthly", "Reminder recurrence set to monthly")
    
    # Completing recurring reminder advances to next cycle
    comp2_res = requests.patch(f"{BASE_URL}/reminders/{rem2['id']}/complete", headers=headers_a)
    assert_test(comp2_res.status_code == 200, "Completing recurring reminder advances to next due date")
    rem2_next = comp2_res.json()
    assert_test(rem2_next.get("reminder_date") > today_str, "Next reminder date correctly advanced")

    # ---------------------------------------------------------
    # 12. RECURRING TRANSACTIONS & IDEMPOTENT GENERATION
    # ---------------------------------------------------------
    print("\n--- 12. RECURRING TRANSACTIONS & IDEMPOTENCY ---")
    # 12.1 Create recurring transaction template
    rec_res = requests.post(f"{BASE_URL}/recurring-transactions", headers=headers_a, json={
        "description": "Gym Membership",
        "amount": 1500.0,
        "type": "expense",
        "category_id": food_cat["id"],
        "frequency": "monthly",
        "payment_method": "Credit Card",
        "start_date": today_str
    })
    assert_test(rec_res.status_code == 201, "User A creates recurring template (201)", rec_res.text)
    rec_item = rec_res.json()
    rec_id = rec_item.get("id")
    assert_test(rec_item.get("status") == "active", "Recurring template status is active")

    # 12.2 Trigger generation via process-now endpoint
    check_due_res = requests.post(f"{BASE_URL}/recurring-transactions/process-now", headers=headers_a)
    assert_test(check_due_res.status_code == 200, "Trigger process-now returns 200")
    gen_data = check_due_res.json()
    gen_count = gen_data.get("generated_count", 0)
    assert_test(gen_count >= 1, "At least 1 transaction generated on due date")

    # 12.3 Verify transaction exists in transactions table and linked to recurring_transaction_id
    tx_data = requests.get(f"{BASE_URL}/transactions", headers=headers_a).json()
    tx_list = tx_data.get("items", [])
    matched_tx = next((t for t in tx_list if t.get("recurring_transaction_id") == rec_id), None)
    assert_test(matched_tx is not None, "Generated transaction linked to recurring_transaction_id")
    if matched_tx:
        assert_test(float(matched_tx["amount"]) == 1500.0, "Generated transaction amount matches template")
    else:
        assert_test(False, "Generated transaction amount matches template", "matched_tx was None")

    # 12.4 Verify Idempotency: Re-running process-now creates ZERO duplicate transactions
    check_due_res2 = requests.post(f"{BASE_URL}/recurring-transactions/process-now", headers=headers_a)
    assert_test(check_due_res2.status_code == 200, "Second check-due returns 200")
    tx_data2 = requests.get(f"{BASE_URL}/transactions", headers=headers_a).json()
    tx_list2 = tx_data2.get("items", [])
    count_matched = len([t for t in tx_list2 if t.get("recurring_transaction_id") == rec_id])
    assert_test(count_matched == 1, "Idempotency verified: exactly 1 transaction generated for this occurrence")

    # 12.5 Pause and Resume
    pause_res = requests.patch(f"{BASE_URL}/recurring-transactions/{rec_id}/pause", headers=headers_a)
    assert_test(pause_res.status_code == 200 and pause_res.json().get("status") == "paused", "User A pauses template")
    resume_res = requests.patch(f"{BASE_URL}/recurring-transactions/{rec_id}/resume", headers=headers_a)
    assert_test(resume_res.status_code == 200 and resume_res.json().get("status") == "active", "User A resumes template")

    # 12.6 User B cannot access User A's recurring template
    b_rec_res = requests.get(f"{BASE_URL}/recurring-transactions/{rec_id}", headers=headers_b)
    assert_test(b_rec_res.status_code == 404, "User B cannot view User A's recurring template (404 isolation)")

    # ---------------------------------------------------------
    # 13. IN-APP NOTIFICATIONS & THRESHOLD ALERTS
    # ---------------------------------------------------------
    print("\n--- 13. IN-APP NOTIFICATIONS & THRESHOLD ALERTS ---")
    # 13.1 Check initial notifications list
    notif_res = requests.get(f"{BASE_URL}/notifications", headers=headers_a)
    assert_test(notif_res.status_code == 200, "GET /api/notifications returns 200")
    unread_res = requests.get(f"{BASE_URL}/notifications/unread-count", headers=headers_a)
    assert_test(unread_res.status_code == 200, "GET /api/notifications/unread-count returns 200")

    # 13.2 Trigger scheduler run which checks budget thresholds, reminders, recurring
    sched_headers = {"X-Scheduler-Key": "expenseflow-scheduler-internal-secret-2026"}
    sched_res = requests.post(f"{BASE_URL}/scheduler/process", headers=sched_headers)
    assert_test(sched_res.status_code == 200, "POST /api/scheduler/process returns 200")

    # 13.3 Test Mark all as read
    read_all_res = requests.patch(f"{BASE_URL}/notifications/read-all", headers=headers_a)
    assert_test(read_all_res.status_code == 200, "PATCH /api/notifications/read-all returns 200")
    unread_after = requests.get(f"{BASE_URL}/notifications/unread-count", headers=headers_a).json().get("unread_count", 0)
    assert_test(unread_after == 0, "Unread count is 0 after mark-all-as-read")

    # 13.4 Isolation: User B cannot see User A's notifications
    b_notifs = requests.get(f"{BASE_URL}/notifications", headers=headers_b).json()
    for n in b_notifs:
        assert_test(n.get("user_id") != user_a_id, "User B notifications strictly isolated from User A")

    # ---------------------------------------------------------
    # 14. PUSH SUBSCRIPTIONS & USER PREFERENCES
    # ---------------------------------------------------------
    print("\n--- 14. PUSH SUBSCRIPTIONS & PREFERENCES ---")
    # 14.1 Get VAPID public key
    pk_res = requests.get(f"{BASE_URL}/push/vapid-public-key", headers=headers_a)
    assert_test(pk_res.status_code == 200, "GET /api/push/vapid-public-key returns 200")
    pubkey = pk_res.json().get("public_key")
    assert_test(bool(pubkey) and len(pubkey) > 20, "Valid VAPID public key string returned")

    # 14.2 Subscribe User A mock push endpoint
    mock_endpoint = f"https://updates.push.services.mozilla.com/wpush/v2/mock_token_{email_a}"
    sub_res = requests.post(f"{BASE_URL}/push/subscribe", headers=headers_a, json={
        "endpoint": mock_endpoint,
        "keys": {
            "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9AcUbVYOEkKIA7vpMeyqDsTJZUpq7st8_p256dh",
            "auth": "mock_auth_secret_123"
        }
    })
    assert_test(sub_res.status_code in [200, 201], "User A subscribes to push (200/201)")

    # 14.3 Re-subscribe (Idempotent upsert)
    sub_res2 = requests.post(f"{BASE_URL}/push/subscribe", headers=headers_a, json={
        "endpoint": mock_endpoint,
        "keys": {
            "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9AcUbVYOEkKIA7vpMeyqDsTJZUpq7st8_p256dh",
            "auth": "mock_auth_secret_123"
        }
    })
    assert_test(sub_res2.status_code in [200, 201], "Re-subscribing is idempotent (no duplicate key error)")

    # 14.4 Preferences: Get and Update
    pref_res = requests.get(f"{BASE_URL}/preferences", headers=headers_a)
    assert_test(pref_res.status_code == 200, "GET /api/preferences returns 200")
    pref_data = pref_res.json()
    assert_test("push_enabled" in pref_data and "budget_alerts" in pref_data, "Preferences contain notification toggles")

    update_pref = requests.put(f"{BASE_URL}/preferences", headers=headers_a, json={
        "push_enabled": True,
        "email_enabled": False,
        "budget_alerts": True,
        "reminder_alerts": True,
        "goal_alerts": True,
        "recurring_alerts": False
    })
    assert_test(update_pref.status_code == 200, "PUT /api/preferences updates preferences")
    assert_test(update_pref.json().get("recurring_alerts") is False, "Updated preference persisted correctly")

    # 14.5 Unsubscribe
    unsub_res = requests.delete(f"{BASE_URL}/push/unsubscribe?endpoint={mock_endpoint}", headers=headers_a)
    assert_test(unsub_res.status_code == 200, "DELETE /api/push/unsubscribe returns 200")

    # ---------------------------------------------------------
    # 15. PWA STATIC ASSETS, MANIFEST & SCHEDULER RUNNER
    # ---------------------------------------------------------
    print("\n--- 15. PWA STATIC SHELL & SCHEDULER RUNNER ---")
    APP_BASE = os.environ.get("TEST_APP_URL", "http://127.0.0.1:8000")
    # 15.1 Web App Manifest
    manifest_res = requests.get(f"{APP_BASE}/manifest.webmanifest")
    assert_test(manifest_res.status_code == 200, "GET /manifest.webmanifest returns 200")
    m_json = manifest_res.json()
    assert_test("ExpenseFlow" in m_json.get("name", "") and m_json.get("short_name") == "ExpenseFlow", "Manifest contains app name ExpenseFlow")
    assert_test(len(m_json.get("icons", [])) >= 3, "Manifest contains required icon definitions")
    assert_test(m_json.get("display") == "standalone", "Manifest display mode is standalone")

    # 15.2 Service Worker
    sw_res = requests.get(f"{APP_BASE}/sw.js")
    assert_test(sw_res.status_code == 200, "GET /sw.js returns 200")
    assert_test("CACHE_NAME" in sw_res.text and "fetch" in sw_res.text, "sw.js contains caching logic")

    # 15.3 Offline Fallback HTML
    off_res = requests.get(f"{APP_BASE}/offline.html")
    assert_test(off_res.status_code == 200, "GET /offline.html returns 200")
    assert_test("Offline" in off_res.text, "offline.html is served")

    # 15.4 PWA Icons
    icon_res = requests.get(f"{APP_BASE}/icons/icon-192.png")
    assert_test(icon_res.status_code == 200, "GET /icons/icon-192.png returns 200")
    assert_test(len(icon_res.content) > 100, "icon-192.png contains binary image data")

    # 15.5 Standalone Scheduler CLI execution
    import subprocess
    sched_proc = subprocess.run(
        [sys.executable, "-m", "app.scheduler"],
        cwd=os.path.join(os.path.dirname(__file__)),
        capture_output=True,
        text=True
    )
    assert_test(sched_proc.returncode == 0, "python -m app.scheduler runs with exit code 0", sched_proc.stderr)


    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"AUTOMATED QA SUITE RESULTS: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 60)
    if failures:
        print("\nFailures:")
        for name, details in failures:
            print(f" - {name}: {details}")
    return failed_count == 0

if __name__ == "__main__":
    success = run_all_qa_tests()
    sys.exit(0 if success else 1)

