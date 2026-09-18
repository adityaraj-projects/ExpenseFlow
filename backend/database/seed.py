"""
ExpenseFlow - Database Seed Script
Populates demo user, default categories, sample transactions, monthly budgets, and savings goals.
Run with: python -m app.database.seed (or python database/seed.py)
"""

import sys
import os
from datetime import date, timedelta
from decimal import Decimal
import random

# Add parent directory to sys.path so app modules are discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import SessionLocal, engine, test_db_connection
from app.database.base import Base
from app.models.user import User
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionType
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal, GoalStatus
from app.core.security import hash_password
from app.services.auth_service import AuthService
from app.core.config import settings


def seed_database():
    print("--------------------------------------------------")
    print("ExpenseFlow — Database Seeder")
    print("--------------------------------------------------")

    if settings.ENVIRONMENT.lower() == "production" and "--force-production" not in sys.argv:
        print("[Security Warning] Seeding demo data is disabled in production environment.")
        print("To override in production, run: python database/seed.py --force-production")
        return

    if not test_db_connection():
        print("[Error] Cannot connect to MySQL. Ensure MySQL server is running and .env is configured.")
        return

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        demo_email = "demo@expenseflow.com"
        existing_user = db.query(User).filter(User.email == demo_email).first()

        if existing_user:
            print(f"[Info] Demo user '{demo_email}' already exists. Skipping recreation.")
            user = existing_user
        else:
            print(f"[Seed] Creating demo user: {demo_email}")
            user = User(
                full_name="Aarav Sharma",
                email=demo_email,
                password_hash=hash_password("Password123!"),
                currency="INR"
            )
            db.add(user)
            db.flush()

            # Seed default categories
            AuthService.seed_default_categories(db, user.id)
            db.commit()
            print("[Seed] Default categories seeded successfully.")

        # Fetch user categories
        categories = db.query(Category).filter(Category.user_id == user.id).all()
        income_cats = [c for c in categories if c.type in [CategoryType.INCOME, CategoryType.BOTH]]
        expense_cats = [c for c in categories if c.type in [CategoryType.EXPENSE, CategoryType.BOTH]]

        cat_by_name = {c.name: c for c in categories}

        # Check existing transactions
        tx_count = db.query(Transaction).filter(Transaction.user_id == user.id).count()
        if tx_count == 0:
            print("[Seed] Generating 90 days of realistic sample transactions...")
            today = date.today()
            sample_transactions = []

            # 1. Monthly Salaries on the 1st of each month
            for m_offset in range(3, -1, -1):
                # approximate salary date
                sal_date = today - timedelta(days=m_offset * 30)
                sal_date = date(sal_date.year, sal_date.month, 1)
                sal_cat = cat_by_name.get("Salary", income_cats[0])

                sample_transactions.append(
                    Transaction(
                        user_id=user.id,
                        category_id=sal_cat.id,
                        type=TransactionType.INCOME,
                        amount=Decimal("85000.00"),
                        description="Monthly Tech Lead Salary",
                        transaction_date=sal_date
                    )
                )

                # Rent on 5th
                rent_cat = cat_by_name.get("Rent & Housing", expense_cats[0])
                sample_transactions.append(
                    Transaction(
                        user_id=user.id,
                        category_id=rent_cat.id,
                        type=TransactionType.EXPENSE,
                        amount=Decimal("24000.00"),
                        description="Apartment Monthly Rent",
                        transaction_date=date(sal_date.year, sal_date.month, 5)
                    )
                )

                # Electricity & Internet on 10th
                bill_cat = cat_by_name.get("Bills & Utilities", expense_cats[0])
                sample_transactions.append(
                    Transaction(
                        user_id=user.id,
                        category_id=bill_cat.id,
                        type=TransactionType.EXPENSE,
                        amount=Decimal("3850.00"),
                        description="Electricity & Fiber Broadband",
                        transaction_date=date(sal_date.year, sal_date.month, 10)
                    )
                )

            # 2. Freelance & Investments
            freelance_cat = cat_by_name.get("Freelance", income_cats[0])
            inv_cat = cat_by_name.get("Investments", income_cats[0])

            sample_transactions.append(
                Transaction(
                    user_id=user.id,
                    category_id=freelance_cat.id,
                    type=TransactionType.INCOME,
                    amount=Decimal("32000.00"),
                    description="Web App UI Design Consultation",
                    transaction_date=today - timedelta(days=18)
                )
            )
            sample_transactions.append(
                Transaction(
                    user_id=user.id,
                    category_id=inv_cat.id,
                    type=TransactionType.INCOME,
                    amount=Decimal("8450.00"),
                    description="Quarterly Mutual Fund Dividend",
                    transaction_date=today - timedelta(days=40)
                )
            )

            # 3. Dynamic everyday expenses over the last 60 days
            expense_templates = [
                ("Groceries", ["Weekly Supermarket Haul - Blinkit", "Organic Veggies & Fruits", "Monthly Pantry Restock", "Dairy & Bakery"], (650, 3200)),
                ("Food & Dining", ["Team Lunch at Social", "Swiggy Gourmet Dinner", "Blue Tokai Coffee & Croissant", "Sunday Family Brunch"], (280, 1850)),
                ("Travel & Commute", ["Uber Cab to Airport", "Metro Card Recharge", "Fuel Petrol Fill-up", "Ola City Ride"], (150, 2400)),
                ("Shopping", ["Uniqlo Linen Shirt", "Amazon Echo Dot Device", "Running Shoes Nike", "Ergonomic Desk Mat"], (799, 4500)),
                ("Entertainment", ["Netflix & Spotify Subscription", "IMAX Movie Tickets - Dune", "PlayStation Plus 3 Months"], (499, 1400)),
                ("Health & Medical", ["Annual Health Checkup Lab", "Pharmacy Prescription Refill", "Gym Membership"], (450, 3000)),
            ]

            for days_ago in range(60, 0, -2):
                tx_date = today - timedelta(days=days_ago)
                # Pick 1 or 2 expenses
                for _ in range(random.choice([1, 2])):
                    cat_name, descs, (min_p, max_p) = random.choice(expense_templates)
                    target_cat = cat_by_name.get(cat_name, expense_cats[0])
                    amt = Decimal(str(random.randint(min_p, max_p)))

                    sample_transactions.append(
                        Transaction(
                            user_id=user.id,
                            category_id=target_cat.id,
                            type=TransactionType.EXPENSE,
                            amount=amt,
                            description=random.choice(descs),
                            transaction_date=tx_date
                        )
                    )

            db.add_all(sample_transactions)
            db.commit()
            print(f"[Seed] Added {len(sample_transactions)} realistic transactions.")
        else:
            print(f"[Info] User already has {tx_count} transactions.")

        # Seed Budgets for current month and previous month
        today = date.today()
        budget_specs = [
            ("Food & Dining", Decimal("12000.00")),
            ("Groceries", Decimal("15000.00")),
            ("Travel & Commute", Decimal("8000.00")),
            ("Shopping", Decimal("10000.00")),
            ("Bills & Utilities", Decimal("6000.00")),
            ("Entertainment", Decimal("5000.00")),
        ]

        for m_val in [today.month, (today.month - 1 if today.month > 1 else 12)]:
            y_val = today.year if m_val <= today.month else today.year - 1
            for cat_name, b_amt in budget_specs:
                c_obj = cat_by_name.get(cat_name)
                if not c_obj:
                    continue
                exists = db.query(Budget).filter(
                    Budget.user_id == user.id,
                    Budget.category_id == c_obj.id,
                    Budget.month == m_val,
                    Budget.year == y_val
                ).first()

                if not exists:
                    db.add(
                        Budget(
                            user_id=user.id,
                            category_id=c_obj.id,
                            amount=b_amt,
                            month=m_val,
                            year=y_val
                        )
                    )
        db.commit()
        print("[Seed] Monthly budgets created.")

        # Seed Savings Goals
        goals_specs = [
            ("Emergency Fund 2026", Decimal("300000.00"), Decimal("185000.00"), today + timedelta(days=180), "6 months essential living expenses cushion", GoalStatus.IN_PROGRESS),
            ("New MacBook Pro M3", Decimal("180000.00"), Decimal("120000.00"), today + timedelta(days=90), "Upgrade primary development workstation", GoalStatus.IN_PROGRESS),
            ("Japan Autumn Vacation", Decimal("250000.00"), Decimal("250000.00"), today + timedelta(days=45), "Flights, hotels and rail pass for Tokyo and Kyoto", GoalStatus.COMPLETED),
            ("Sovereign Gold Bonds", Decimal("100000.00"), Decimal("45000.00"), today + timedelta(days=240), "Long term precious metals hedge", GoalStatus.IN_PROGRESS)
        ]

        for g_name, g_target, g_curr, g_date, g_desc, g_status in goals_specs:
            exists = db.query(SavingsGoal).filter(
                SavingsGoal.user_id == user.id,
                SavingsGoal.name == g_name
            ).first()

            if not exists:
                db.add(
                    SavingsGoal(
                        user_id=user.id,
                        name=g_name,
                        target_amount=g_target,
                        current_amount=g_curr,
                        target_date=g_date,
                        description=g_desc,
                        status=g_status
                    )
                )
        db.commit()
        print("[Seed] Savings goals created.")

        print("--------------------------------------------------")
        print("SEEDING COMPLETED SUCCESSFULLY!")
        print("Demo Credentials:")
        print(f"  Email:    {demo_email}")
        print("  Password: Password123!")
        print("--------------------------------------------------")

    except Exception as e:
        db.rollback()
        print(f"[Error] Failed to seed database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
