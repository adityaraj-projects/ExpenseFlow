import json
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.user import User
from app.models.user_preference import UserPreference
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.models.budget import Budget
from app.models.savings_goal import SavingsGoal
from app.models.reminder import Reminder, ReminderStatus
from app.models.recurring_transaction import RecurringTransaction, RecurringStatus, RecurringFrequency
from app.schemas.backup import (
    BackupPayload,
    BackupUser,
    BackupCategory,
    BackupTransaction,
    BackupBudget,
    BackupSavingsGoal,
    BackupReminder,
    BackupRecurring,
    BackupValidateResponse,
    RestoreItemSummary,
    BackupRestoreResponse
)


def _compute_tx_fingerprint(
    user_id: int,
    tx_date: str,
    tx_time: Optional[str],
    amount: Decimal,
    tx_type: str,
    description: str
) -> str:
    clean_desc = re.sub(r'[^a-zA-Z0-9]', '', description).lower()
    clean_time = (tx_time or "").strip().lower()
    clean_amt = f"{Decimal(str(amount)):.2f}"
    clean_type = tx_type.strip().lower()
    return f"{user_id}|{tx_date}|{clean_time}|{clean_amt}|{clean_type}|{clean_desc}"


class BackupService:

    @classmethod
    def export_backup(cls, db: Session, user: User) -> Dict[str, Any]:
        """
        Creates a versioned, privacy-safe JSON backup dictionary for the authenticated user.
        Excludes sensitive data (passwords, JWT secrets, VAPID keys, tokens).
        """
        # 1. User preferences
        pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
        pref_dict = {
            "notifications_enabled": pref.notifications_enabled if pref else True,
            "budget_alerts": pref.budget_alerts if pref else True,
            "reminder_alerts": pref.reminder_alerts if pref else True,
            "goal_alerts": pref.goal_alerts if pref else True,
            "recurring_alerts": pref.recurring_alerts if pref else True,
            "push_enabled": pref.push_enabled if pref else True,
            "monthly_summary_alerts": getattr(pref, "monthly_summary_alerts", True) if pref else True,
        }

        # 2. Categories
        categories = db.query(Category).filter(
            or_(Category.user_id == user.id, Category.user_id.is_(None))
        ).all()
        categories_data = [
            {
                "name": c.name,
                "type": c.type.value if hasattr(c.type, 'value') else str(c.type),
                "color": c.color,
                "icon": c.icon
            }
            for c in categories
        ]

        # 3. Transactions
        transactions = db.query(Transaction).filter(
            Transaction.user_id == user.id
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()
        transactions_data = [
            {
                "amount": float(t.amount),
                "type": t.type.value if hasattr(t.type, 'value') else str(t.type),
                "transaction_date": t.transaction_date.isoformat(),
                "transaction_time": t.transaction_time,
                "description": t.description,
                "category_name": t.category.name if t.category else None,
                "source": t.source or "manual",
                "source_reference": t.source_reference,
                "external_transaction_id": t.external_transaction_id,
                "external_utr": t.external_utr,
                "notes": getattr(t, "notes", None)
            }
            for t in transactions
        ]

        # 4. Budgets
        budgets = db.query(Budget).filter(Budget.user_id == user.id).all()
        budgets_data = [
            {
                "category_name": b.category.name if b.category else "Uncategorized",
                "amount": float(b.amount),
                "month": b.month,
                "year": b.year
            }
            for b in budgets
        ]

        # 5. Savings Goals
        goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == user.id).all()
        goals_data = [
            {
                "name": g.name,
                "target_amount": float(g.target_amount),
                "current_amount": float(g.current_amount or 0),
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "status": g.status.value if hasattr(g.status, 'value') else str(g.status)
            }
            for g in goals
        ]

        # 6. Reminders
        reminders = db.query(Reminder).filter(Reminder.user_id == user.id).all()
        reminders_data = [
            {
                "title": r.title,
                "amount": float(r.amount) if r.amount else None,
                "reminder_date": r.reminder_date.isoformat(),
                "category_name": r.category.name if r.category else None,
                "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
                "notes": getattr(r, "notes", r.description)
            }
            for r in reminders
        ]

        # 7. Recurring Transactions
        recurring = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user.id).all()
        recurring_data = [
            {
                "description": rec.description,
                "amount": float(rec.amount),
                "type": rec.type.value if hasattr(rec.type, 'value') else str(rec.type),
                "frequency": rec.frequency.value if hasattr(rec.frequency, 'value') else str(rec.frequency),
                "category_name": rec.category.name if rec.category else None,
                "start_date": rec.start_date.isoformat() if rec.start_date else None,
                "next_occurrence_date": rec.next_occurrence_date.isoformat() if rec.next_occurrence_date else None,
                "status": rec.status.value if hasattr(rec.status, 'value') else str(rec.status)
            }
            for rec in recurring
        ]

        return {
            "application": "ExpenseFlow",
            "backup_version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "user": {
                "name": getattr(user, "full_name", "User"),
                "email": user.email,
                "currency": user.currency or "INR"
            },
            "notification_preferences": pref_dict,
            "categories": categories_data,
            "transactions": transactions_data,
            "budgets": budgets_data,
            "savings_goals": goals_data,
            "reminders": reminders_data,
            "recurring_transactions": recurring_data
        }

    @classmethod
    def validate_backup_payload(cls, data: Dict[str, Any]) -> BackupValidateResponse:
        """
        Validates backup integrity, schema compliance, and calculates item counts.
        """
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Invalid backup file: root must be a JSON object.")

        app_name = data.get("application")
        if app_name != "ExpenseFlow":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported backup file: expected ExpenseFlow backup, found '{app_name}'."
            )

        version = str(data.get("backup_version", ""))
        if version not in ["1.0"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported backup version '{version}'. Only version 1.0 is currently supported."
            )

        counts = {
            "categories": len(data.get("categories", [])),
            "transactions": len(data.get("transactions", [])),
            "budgets": len(data.get("budgets", [])),
            "savings_goals": len(data.get("savings_goals", [])),
            "reminders": len(data.get("reminders", [])),
            "recurring_transactions": len(data.get("recurring_transactions", []))
        }

        user_info = data.get("user") or {}
        user_name = user_info.get("name") if isinstance(user_info, dict) else None

        return BackupValidateResponse(
            valid=True,
            application=app_name,
            backup_version=version,
            created_at=data.get("created_at"),
            user_name=user_name,
            counts=counts,
            message="Backup file validated successfully and ready for restore."
        )

    @classmethod
    def restore_backup(cls, db: Session, user_id: int, payload: BackupPayload) -> BackupRestoreResponse:
        """
        Restores backup data strictly scoped to the authenticated user ID.
        Applies duplicate protection to prevent duplicate transactions, budgets, goals, etc.
        """
        summary = {
            "categories": {"imported": 0, "skipped": 0, "failed": 0},
            "transactions": {"imported": 0, "skipped": 0, "failed": 0},
            "budgets": {"imported": 0, "skipped": 0, "failed": 0},
            "savings_goals": {"imported": 0, "skipped": 0, "failed": 0},
            "reminders": {"imported": 0, "skipped": 0, "failed": 0},
            "recurring_transactions": {"imported": 0, "skipped": 0, "failed": 0}
        }

        # 1. Categories Mapping & Creation
        existing_cats = db.query(Category).filter(
            or_(Category.user_id == user_id, Category.user_id.is_(None))
        ).all()
        # Key: (name_lower, type_lower) -> Category instance
        cat_map = {}
        for c in existing_cats:
            t_str = c.type.value if hasattr(c.type, 'value') else str(c.type)
            cat_map[(c.name.strip().lower(), t_str.strip().lower())] = c

        for cat_item in payload.categories:
            try:
                name_clean = cat_item.name.strip()
                type_clean = cat_item.type.strip().lower()
                key = (name_clean.lower(), type_clean)
                if key in cat_map:
                    summary["categories"]["skipped"] += 1
                else:
                    new_cat = Category(
                        user_id=user_id,
                        name=name_clean,
                        type=type_clean,
                        color=cat_item.color or "#64748B",
                        icon=cat_item.icon or "tag"
                    )
                    db.add(new_cat)
                    db.flush()
                    cat_map[key] = new_cat
                    summary["categories"]["imported"] += 1
            except Exception:
                summary["categories"]["failed"] += 1

        # 2. Transactions Deduplication & Insertion
        existing_txs = db.query(Transaction).filter(Transaction.user_id == user_id).all()
        existing_ext_ids = {t.external_transaction_id for t in existing_txs if t.external_transaction_id}
        existing_utrs = {t.external_utr for t in existing_txs if t.external_utr}
        existing_fingerprints = set()
        for t in existing_txs:
            t_type_str = t.type.value if hasattr(t.type, 'value') else str(t.type)
            existing_fingerprints.add(_compute_tx_fingerprint(
                user_id=user_id,
                tx_date=t.transaction_date.isoformat(),
                tx_time=t.transaction_time,
                amount=t.amount,
                tx_type=t_type_str,
                description=t.description
            ))

        for tx_item in payload.transactions:
            try:
                # Priority 1: External Transaction ID
                if tx_item.external_transaction_id and tx_item.external_transaction_id in existing_ext_ids:
                    summary["transactions"]["skipped"] += 1
                    continue

                # Priority 2: External UTR
                if tx_item.external_utr and tx_item.external_utr in existing_utrs:
                    summary["transactions"]["skipped"] += 1
                    continue

                # Priority 3: Deterministic Fingerprint
                fp = _compute_tx_fingerprint(
                    user_id=user_id,
                    tx_date=tx_item.transaction_date,
                    tx_time=tx_item.transaction_time,
                    amount=tx_item.amount,
                    tx_type=tx_item.type,
                    description=tx_item.description
                )
                if fp in existing_fingerprints:
                    summary["transactions"]["skipped"] += 1
                    continue

                # Resolve Category
                cat_id = None
                tx_type = tx_item.type.strip().lower()
                if tx_item.category_name:
                    c_key = (tx_item.category_name.strip().lower(), tx_type)
                    if c_key in cat_map:
                        cat_id = cat_map[c_key].id

                if not cat_id:
                    for (cname, ctype), cat_obj in cat_map.items():
                        if ctype == tx_type:
                            cat_id = cat_obj.id
                            break
                    if not cat_id:
                        fallback_name = "Other Expense" if tx_type == "expense" else "Other Income"
                        new_cat = Category(
                            user_id=user_id,
                            name=fallback_name,
                            type=tx_type,
                            color="#64748B",
                            icon="tag"
                        )
                        db.add(new_cat)
                        db.flush()
                        cat_map[(fallback_name.lower(), tx_type)] = new_cat
                        cat_id = new_cat.id

                # Parse date
                try:
                    tx_dt = datetime.strptime(tx_item.transaction_date, "%Y-%m-%d").date()
                except ValueError:
                    tx_dt = date.today()

                new_tx = Transaction(
                    user_id=user_id,
                    amount=Decimal(str(tx_item.amount)),
                    type=tx_type,
                    transaction_date=tx_dt,
                    transaction_time=tx_item.transaction_time,
                    description=tx_item.description.strip(),
                    category_id=cat_id,
                    source=tx_item.source or "manual",
                    source_reference=tx_item.source_reference,
                    external_transaction_id=tx_item.external_transaction_id,
                    external_utr=tx_item.external_utr
                )
                db.add(new_tx)
                existing_fingerprints.add(fp)
                if tx_item.external_transaction_id:
                    existing_ext_ids.add(tx_item.external_transaction_id)
                if tx_item.external_utr:
                    existing_utrs.add(tx_item.external_utr)
                summary["transactions"]["imported"] += 1
            except Exception:
                summary["transactions"]["failed"] += 1

        # 3. Budgets Deduplication & Insertion
        existing_budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
        # Key: (category_id, month, year)
        b_keys = {(b.category_id, b.month, b.year) for b in existing_budgets}

        for b_item in payload.budgets:
            try:
                # Find category
                b_cat = None
                if b_item.category_name:
                    for (cname, ctype), cat_obj in cat_map.items():
                        if cname == b_item.category_name.strip().lower() and ctype == "expense":
                            b_cat = cat_obj
                            break

                cat_id = b_cat.id if b_cat else None
                b_key = (cat_id, b_item.month, b_item.year)
                if b_key in b_keys:
                    summary["budgets"]["skipped"] += 1
                else:
                    new_b = Budget(
                        user_id=user_id,
                        category_id=cat_id,
                        amount=Decimal(str(b_item.amount)),
                        month=b_item.month,
                        year=b_item.year
                    )
                    db.add(new_b)
                    b_keys.add(b_key)
                    summary["budgets"]["imported"] += 1
            except Exception:
                summary["budgets"]["failed"] += 1

        # 4. Savings Goals Deduplication & Insertion
        existing_goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).all()
        goal_names = {g.name.strip().lower() for g in existing_goals}

        for g_item in payload.savings_goals:
            try:
                g_name_clean = g_item.name.strip().lower()
                if g_name_clean in goal_names:
                    summary["savings_goals"]["skipped"] += 1
                else:
                    t_date = None
                    if g_item.target_date:
                        try:
                            t_date = datetime.strptime(g_item.target_date, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                    new_g = SavingsGoal(
                        user_id=user_id,
                        name=g_item.name.strip(),
                        target_amount=Decimal(str(g_item.target_amount)),
                        current_amount=Decimal(str(g_item.current_amount or "0.00")),
                        target_date=t_date,
                        status=g_item.status or "in_progress"
                    )
                    db.add(new_g)
                    goal_names.add(g_name_clean)
                    summary["savings_goals"]["imported"] += 1
            except Exception:
                summary["savings_goals"]["failed"] += 1

        # 5. Reminders Deduplication & Insertion
        existing_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).all()
        rem_keys = {(r.title.strip().lower(), r.reminder_date.isoformat()) for r in existing_reminders}

        for r_item in payload.reminders:
            try:
                r_key = (r_item.title.strip().lower(), r_item.reminder_date)
                if r_key in rem_keys:
                    summary["reminders"]["skipped"] += 1
                else:
                    try:
                        r_dt = datetime.strptime(r_item.reminder_date, "%Y-%m-%d").date()
                    except ValueError:
                        r_dt = date.today()

                    r_cat_id = None
                    if r_item.category_name:
                        for (cname, ctype), cat_obj in cat_map.items():
                            if cname == r_item.category_name.strip().lower():
                                r_cat_id = cat_obj.id
                                break

                    new_r = Reminder(
                        user_id=user_id,
                        title=r_item.title.strip(),
                        description=r_item.notes or None,
                        amount=Decimal(str(r_item.amount)) if r_item.amount else None,
                        reminder_date=r_dt,
                        category_id=r_cat_id,
                        status=r_item.status or "pending"
                    )
                    db.add(new_r)
                    rem_keys.add(r_key)
                    summary["reminders"]["imported"] += 1
            except Exception:
                summary["reminders"]["failed"] += 1

        # 6. Recurring Transactions Deduplication & Insertion
        existing_recurring = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user_id).all()
        rec_keys = {(rec.description.strip().lower(), f"{Decimal(str(rec.amount)):.2f}", rec.type.lower() if hasattr(rec.type, 'lower') else str(rec.type).lower()) for rec in existing_recurring}

        for rec_item in payload.recurring_transactions:
            try:
                amt_str = f"{Decimal(str(rec_item.amount)):.2f}"
                rec_type = rec_item.type.strip().lower()
                rec_key = (rec_item.description.strip().lower(), amt_str, rec_type)
                if rec_key in rec_keys:
                    summary["recurring_transactions"]["skipped"] += 1
                else:
                    rec_cat_id = None
                    if rec_item.category_name:
                        c_lookup = (rec_item.category_name.strip().lower(), rec_type)
                        if c_lookup in cat_map:
                            rec_cat_id = cat_map[c_lookup].id

                    if not rec_cat_id:
                        for (cname, ctype), cat_obj in cat_map.items():
                            if ctype == rec_type:
                                rec_cat_id = cat_obj.id
                                break
                        if not rec_cat_id:
                            fallback_name = "Other Expense" if rec_type == "expense" else "Other Income"
                            new_cat = Category(
                                user_id=user_id,
                                name=fallback_name,
                                type=rec_type,
                                color="#64748B",
                                icon="tag"
                            )
                            db.add(new_cat)
                            db.flush()
                            cat_map[(fallback_name.lower(), rec_type)] = new_cat
                            rec_cat_id = new_cat.id

                    start_dt = date.today()
                    if rec_item.start_date:
                        try:
                            start_dt = datetime.strptime(rec_item.start_date, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                    next_dt = start_dt
                    if rec_item.next_occurrence_date:
                        try:
                            next_dt = datetime.strptime(rec_item.next_occurrence_date, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                    new_rec = RecurringTransaction(
                        user_id=user_id,
                        description=rec_item.description.strip(),
                        amount=Decimal(str(rec_item.amount)),
                        type=rec_type,
                        frequency=rec_item.frequency.strip().lower(),
                        category_id=rec_cat_id,
                        payment_method="Other",
                        start_date=start_dt,
                        next_occurrence_date=next_dt,
                        status=rec_item.status or "active"
                    )
                    db.add(new_rec)
                    rec_keys.add(rec_key)
                    summary["recurring_transactions"]["imported"] += 1
            except Exception:
                summary["recurring_transactions"]["failed"] += 1

        # 7. Notification Preferences Restore
        if payload.notification_preferences:
            pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if not pref:
                pref = UserPreference(user_id=user_id)
                db.add(pref)

            for key, val in payload.notification_preferences.items():
                if hasattr(pref, key) and isinstance(val, bool):
                    setattr(pref, key, val)

        # Commit all changes atomically
        db.commit()

        total_imported = sum(s["imported"] for s in summary.values())
        total_skipped = sum(s["skipped"] for s in summary.values())
        total_failed = sum(s["failed"] for s in summary.values())

        typed_summary = {
            k: RestoreItemSummary(
                imported=v["imported"],
                skipped=v["skipped"],
                failed=v["failed"]
            )
            for k, v in summary.items()
        }

        return BackupRestoreResponse(
            status="success",
            summary=typed_summary,
            total_imported=total_imported,
            total_skipped=total_skipped,
            total_failed=total_failed,
            message=f"Backup restored successfully: {total_imported} records imported, {total_skipped} existing records skipped."
        )
