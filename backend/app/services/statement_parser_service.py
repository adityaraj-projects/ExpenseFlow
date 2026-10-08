import re
import io
import logging
from datetime import datetime, date as dt_date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import PyPDF2
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException, status
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category, CategoryType
from app.models.statement_import import StatementImport

logger = logging.getLogger(__name__)


def parse_phonepe_date(date_str: str) -> str:
    """Normalize various PhonePe date formats into standard YYYY-MM-DD string."""
    cleaned = date_str.strip()
    cleaned = re.sub(r'\bSept\b', 'Sep', cleaned, flags=re.IGNORECASE)
    formats = [
        '%b %d, %Y', '%b %d %Y', '%B %d, %Y', '%B %d %Y',
        '%d %b, %Y', '%d %b %Y', '%d %B, %Y', '%d %B %Y',
        '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return cleaned


def parse_phonepe_time(time_str: str) -> str:
    """Normalize 12-hour or 24-hour time strings into standard hh:mm AM/PM format."""
    cleaned = time_str.strip()
    formats = ['%I:%M %p', '%I:%M%p', '%H:%M']
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned.upper(), fmt)
            return dt.strftime('%I:%M %p')
        except ValueError:
            pass
    return cleaned


KEYWORD_CATEGORY_MAP = {
    # Food & Dining
    "food": "Food & Dining",
    "dining": "Food & Dining",
    "pizza": "Food & Dining",
    "restaurant": "Food & Dining",
    "cafe": "Food & Dining",
    "parlour": "Food & Dining",
    "parlor": "Food & Dining",
    "kitchen": "Food & Dining",
    "burger": "Food & Dining",
    "tea": "Food & Dining",
    "coffee": "Food & Dining",
    "dhaba": "Food & Dining",
    "biryani": "Food & Dining",
    "bakery": "Food & Dining",
    "sweets": "Food & Dining",
    "juice": "Food & Dining",
    "zomato": "Food & Dining",
    "swiggy": "Food & Dining",
    "goodness by naira": "Food & Dining",

    # Shopping
    "ekart": "Shopping",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "shop": "Shopping",
    "retail": "Shopping",
    "cloth": "Shopping",
    "fashion": "Shopping",
    "trends": "Shopping",
    "zudio": "Shopping",
    "mall": "Shopping",

    # Rent & Housing
    "hostel": "Rent & Housing",
    "rent": "Rent & Housing",
    "room": "Rent & Housing",
    "pg": "Rent & Housing",
    "stay": "Rent & Housing",
    "housing": "Rent & Housing",

    # Travel & Commute
    "travel": "Travel & Commute",
    "commute": "Travel & Commute",
    "metro": "Travel & Commute",
    "bus": "Travel & Commute",
    "train": "Travel & Commute",
    "irctc": "Travel & Commute",
    "uber": "Travel & Commute",
    "ola": "Travel & Commute",
    "auto": "Travel & Commute",
    "rapido": "Travel & Commute",
    "petrol": "Travel & Commute",
    "fuel": "Travel & Commute",
    "diesel": "Travel & Commute",
    "toll": "Travel & Commute",

    # Bills & Utilities
    "airtel": "Bills & Utilities",
    "jio": "Bills & Utilities",
    "vi": "Bills & Utilities",
    "telecom": "Bills & Utilities",
    "recharge": "Bills & Utilities",
    "recharged": "Bills & Utilities",
    "autopay": "Bills & Utilities",
    "electric": "Bills & Utilities",
    "electricity": "Bills & Utilities",
    "broadband": "Bills & Utilities",
    "wifi": "Bills & Utilities",
    "dth": "Bills & Utilities",
    "dashreels": "Bills & Utilities",
    "google": "Bills & Utilities",
    "subscription": "Bills & Utilities",
    "gas": "Bills & Utilities",

    # Education
    "pu": "Education",
    "university": "Education",
    "college": "Education",
    "school": "Education",
    "tuition": "Education",
    "classmate": "Education",
    "institute": "Education",
    "exam": "Education",
    "mca": "Education",

    # Health & Medical
    "pharmacy": "Health & Medical",
    "hospital": "Health & Medical",
    "clinic": "Health & Medical",
    "chemist": "Health & Medical",
    "medical": "Health & Medical",
    "doctor": "Health & Medical",
    "health": "Health & Medical",

    # Entertainment
    "netflix": "Entertainment",
    "cinema": "Entertainment",
    "movie": "Entertainment",
    "bookmyshow": "Entertainment",
    "hotstar": "Entertainment",
    "spotify": "Entertainment",

    # Groceries
    "supermart": "Groceries",
    "kirana": "Groceries",
    "grocery": "Groceries",
    "mart": "Groceries",
    "provision": "Groceries",
    "dairy": "Groceries",
    "milk": "Groceries",

    # Income
    "salary": "Salary",
    "payroll": "Salary",
    "freelance": "Freelance",
    "upwork": "Freelance",
    "fiverr": "Freelance",
    "cashback": "Other Income",
    "reward": "Other Income",
    "refund": "Other Income",
}


def make_transaction_fingerprint(
    user_id: int,
    tx_date: str,
    tx_time: Optional[str],
    amount: Decimal,
    tx_type: str,
    description: str
) -> str:
    """Generate deterministic fingerprint for duplicate matching when external IDs are missing."""
    clean_desc = re.sub(r'[^a-zA-Z0-9]', '', description).lower()
    clean_time = (tx_time or "").strip().lower()
    clean_amt = f"{amount:.2f}"
    return f"{user_id}|{tx_date}|{clean_time}|{clean_amt}|{tx_type}|{clean_desc}"


class StatementParserService:
    @staticmethod
    def validate_pdf_bytes(pdf_bytes: bytes, filename: str) -> None:
        """Validate file size, extension, and PDF header magic bytes."""
        if not filename.lower().endswith(".pdf"):
            logger.warning("Upload validation failed: file %s is not a PDF", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files (.pdf) are supported. Please upload a valid PhonePe statement."
            )
        if len(pdf_bytes) == 0:
            logger.warning("Upload validation failed: file %s is empty", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF file is empty."
            )
        # Limit to 15MB
        if len(pdf_bytes) > 15 * 1024 * 1024:
            logger.warning("Upload validation failed: file %s exceeds 15MB (%d bytes)", filename, len(pdf_bytes))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the 15MB limit. Please upload a smaller PDF statement."
            )
        # Magic bytes check
        if not pdf_bytes.startswith(b"%PDF"):
            logger.warning("Upload validation failed: file %s lacks %PDF magic header", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file does not appear to be a valid PDF document."
            )
        logger.info("PDF file %s (%d bytes) passed basic validation", filename, len(pdf_bytes))

    @staticmethod
    def extract_phonepe_raw_transactions(pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse raw text from PhonePe PDF statement and extract transactions."""
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            if reader.is_encrypted:
                try:
                    # Attempt empty password decryption
                    reader.decrypt("")
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The uploaded PDF is password protected. Please remove the password and try again."
                    )
            full_text = ""
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                full_text += f"\n" + page_text
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to read PDF pages: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not read PDF contents. Please ensure the file is not corrupted."
            )

        logger.info("Extracted %d characters of raw text from PDF", len(full_text))

        # Pre-clean known PhonePe statement repeating headers, footers, and table headings
        # so transactions crossing page boundaries stitch seamlessly together
        clean_text = re.sub(r'Page \d+ of \d+\s*\n[^\n]*\nhttps://support\.phonepe\.com[^\n]*', '', full_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Transaction Statement for [^\n]+', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*,?\s+\d{4}\s*-\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*,?\s+\d{4}', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'Date\s*\n\s*Transaction Details\s*\n\s*Type\s*\n\s*Amount', '', clean_text, flags=re.IGNORECASE)

        # Regex matching PhonePe statement transaction blocks:
        # 1. Date: e.g. "Oct 02, 2026" or "Sept 30, 2026" or "02 Sept, 2026"
        # 2. Time: e.g. "05:07 pm" or "10:30 am"
        # 3. Type: DEBIT or CREDIT
        # 4. Currency: ₹
        # 5. Amount: e.g. 30 or 1,299.50 or 40,000
        # 6. Description / Party block (matches across lines and emojis until Transaction ID)
        # 7. Transaction ID (starts with T, OM, NB, OLEX, etc.)
        # 8. Optional UTR No.
        tx_pattern = re.compile(
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*,?\s+\d{4})\s*\n'
            r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\s*\n'
            r'(DEBIT|CREDIT)\s*\n'
            r'₹\s*\n'
            r'([\d,]+(?:\.\d{1,2})?)\s*\n'
            r'([\s\S]*?)\s*\n'
            r'Transaction ID\s+([A-Za-z0-9]+)'
            r'(?:\s*\nUTR No\.\s*([A-Za-z0-9]+))?',
            re.IGNORECASE
        )

        matches = list(tx_pattern.finditer(clean_text))
        logger.info("Found %d transaction pattern matches in statement text", len(matches))

        extracted: List[Dict[str, Any]] = []
        for match in matches:
            raw_date = match.group(1).strip()
            raw_time = match.group(2).strip()
            tx_type_raw = match.group(3).strip().upper()
            amount_raw = match.group(4).strip().replace(',', '')
            desc_block = match.group(5).strip()
            tx_id = match.group(6).strip()
            utr = match.group(7).strip() if match.group(7) else None

            # Collapse multiline party block into clean single-line description
            desc_cleaned = ' '.join(desc_block.split()).strip()

            # Clean action prefix and party name
            party_match = re.match(
                r'^(Paid to|Received from|Payment to|Refund from|Transfer to|Money sent to|Paid by|Sent to|AutoPay activation|Mobile recharged|Bill payment to)\s*(.*)',
                desc_cleaned,
                re.IGNORECASE
            )
            if party_match:
                action_prefix = party_match.group(1).strip()
                party_name = party_match.group(2).strip() or action_prefix
            else:
                action_prefix = "Paid to" if tx_type_raw == "DEBIT" else "Received from"
                party_name = desc_cleaned

            # Standardized date YYYY-MM-DD
            formatted_date = parse_phonepe_date(raw_date)

            # Standardized time hh:mm AM/PM
            formatted_time = parse_phonepe_time(raw_time)

            tx_type = "expense" if tx_type_raw == "DEBIT" else "income"
            amount = Decimal(amount_raw)

            full_desc = desc_cleaned if desc_cleaned else (f"{action_prefix} {party_name}".strip() if action_prefix else party_name)

            extracted.append({
                "raw_date": raw_date,
                "transaction_date": formatted_date,
                "raw_time": raw_time,
                "transaction_time": formatted_time,
                "type": tx_type,
                "amount": amount,
                "description": full_desc,
                "merchant_or_party": party_name,
                "external_transaction_id": tx_id,
                "external_utr": utr,
                "source": "phonepe"
            })

        logger.info("Successfully extracted %d raw PhonePe transactions", len(extracted))
        return extracted

    @staticmethod
    def suggest_category_for_transaction(
        tx_type: str,
        party_name: str,
        description: str,
        user_categories: List[Category]
    ) -> Tuple[int, str, str, str]:
        """
        Suggests an appropriate category from the user's existing categories
        based on merchant/party name and description keywords.
        Returns: (category_id, category_name, category_icon, category_color)
        """
        combined_text = f"{party_name} {description}".lower()

        # 1. Determine best keyword match category target name
        target_name: Optional[str] = None
        for kw, cat_name in KEYWORD_CATEGORY_MAP.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', combined_text):
                target_name = cat_name
                break

        # Filter user categories compatible with this transaction type
        target_type_enum = CategoryType.EXPENSE if tx_type == "expense" else CategoryType.INCOME
        compatible_cats = [
            c for c in user_categories
            if c.type == CategoryType.BOTH or c.type == target_type_enum
        ]

        if not compatible_cats:
            # Fallback if user has no matching type categories (unlikely)
            first_cat = user_categories[0] if user_categories else None
            if first_cat:
                return first_cat.id, first_cat.name, first_cat.icon, first_cat.color
            return 1, "Other Expense" if tx_type == "expense" else "Other Income", "tag", "#64748B"

        # 2. If target name identified, search user categories for direct or partial match
        if target_name:
            for cat in compatible_cats:
                if cat.name.lower() == target_name.lower():
                    return cat.id, cat.name, cat.icon, cat.color

            # Partial word match (e.g. target "Bills & Utilities" matches user's "Bills" or "Utilities")
            target_words = set(re.findall(r'\w+', target_name.lower()))
            for cat in compatible_cats:
                cat_words = set(re.findall(r'\w+', cat.name.lower()))
                if target_words.intersection(cat_words) - {"and", "other"}:
                    return cat.id, cat.name, cat.icon, cat.color

        # 3. Fallback: Find user's "Other Expense" or "Other Income"
        fallback_name = "Other Expense" if tx_type == "expense" else "Other Income"
        for cat in compatible_cats:
            if cat.name.lower() == fallback_name.lower():
                return cat.id, cat.name, cat.icon, cat.color

        # 4. Final fallback: Pick first compatible category
        first_match = compatible_cats[0]
        return first_match.id, first_match.name, first_match.icon, first_match.color

    @classmethod
    def parse_statement_preview(
        cls,
        db: Session,
        user_id: int,
        pdf_bytes: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Validates, parses, deduplicates against user transactions,
        and generates an interactive preview for user confirmation.
        """
        cls.validate_pdf_bytes(pdf_bytes, filename)
        raw_txs = cls.extract_phonepe_raw_transactions(pdf_bytes)

        if not raw_txs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No PhonePe transactions could be detected from this PDF. Please ensure you uploaded a valid PhonePe transaction statement."
            )

        # Fetch user's categories for suggestion and selection
        user_categories = db.query(Category).filter(Category.user_id == user_id).all()
        categories_dict = [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type.value,
                "icon": c.icon,
                "color": c.color
            }
            for c in user_categories
        ]

        # Fetch existing user transactions for duplicate detection
        existing_txs = db.query(
            Transaction.external_transaction_id,
            Transaction.external_utr,
            Transaction.transaction_date,
            Transaction.transaction_time,
            Transaction.amount,
            Transaction.type,
            Transaction.description
        ).filter(Transaction.user_id == user_id).all()

        existing_tx_ids = {
            t.external_transaction_id.strip()
            for t in existing_txs
            if t.external_transaction_id
        }
        existing_utrs = {
            t.external_utr.strip()
            for t in existing_txs
            if t.external_utr
        }
        existing_fingerprints = {
            make_transaction_fingerprint(
                user_id=user_id,
                tx_date=str(t.transaction_date),
                tx_time=t.transaction_time,
                amount=t.amount,
                tx_type=t.type.value,
                description=t.description
            )
            for t in existing_txs
        }

        preview_items: List[Dict[str, Any]] = []
        new_count = 0
        duplicate_count = 0

        # Also track within the same statement to detect any internal repeats
        seen_in_statement_tx_ids = set()
        seen_in_statement_utrs = set()
        seen_in_statement_fingerprints = set()

        for idx, tx in enumerate(raw_txs):
            tx_id = (tx["external_transaction_id"] or "").strip()
            utr = (tx["external_utr"] or "").strip()
            tx_date_str = str(tx["transaction_date"])
            tx_time_str = tx["transaction_time"]
            amt = tx["amount"]
            tx_type = tx["type"]
            desc = tx["description"]

            fg = make_transaction_fingerprint(user_id, tx_date_str, tx_time_str, amt, tx_type, desc)

            # Check duplicate matching priority:
            # 1. Transaction ID (if present)
            # 2. UTR number (if present and tx_id missing)
            # 3. Deterministic transaction fingerprint (only when external IDs are not present)
            is_dup = False
            dup_reason = ""
            if tx_id:
                if tx_id in existing_tx_ids or tx_id in seen_in_statement_tx_ids:
                    is_dup = True
                    dup_reason = "Transaction ID already exists in your account"
            elif utr:
                if utr in existing_utrs or utr in seen_in_statement_utrs:
                    is_dup = True
                    dup_reason = "UTR number already exists in your account"
            else:
                if fg in existing_fingerprints or fg in seen_in_statement_fingerprints:
                    is_dup = True
                    dup_reason = "Matching transaction already recorded"

            if tx_id:
                seen_in_statement_tx_ids.add(tx_id)
            if utr:
                seen_in_statement_utrs.add(utr)
            seen_in_statement_fingerprints.add(fg)

            if is_dup:
                duplicate_count += 1
                status_label = "Already Imported"
                is_selected = False
            else:
                new_count += 1
                status_label = "New"
                is_selected = True

            cat_id, cat_name, cat_icon, cat_color = cls.suggest_category_for_transaction(
                tx_type=tx_type,
                party_name=tx["merchant_or_party"],
                description=desc,
                user_categories=user_categories
            )

            preview_items.append({
                "preview_id": f"p_{idx}",
                "transaction_date": tx_date_str,
                "transaction_time": tx_time_str,
                "type": tx_type,
                "amount": float(amt),
                "description": desc,
                "merchant_or_party": tx["merchant_or_party"],
                "external_transaction_id": tx_id,
                "external_utr": utr,
                "source": "phonepe",
                "suggested_category_id": cat_id,
                "suggested_category_name": cat_name,
                "suggested_category_icon": cat_icon,
                "suggested_category_color": cat_color,
                "is_duplicate": is_dup,
                "duplicate_reason": dup_reason,
                "status": status_label,
                "is_selected": is_selected
            })

        logger.info(
            "Statement preview parsed for user_id=%d: total=%d, new=%d, duplicates=%d",
            user_id, len(raw_txs), new_count, duplicate_count
        )

        return {
            "statement_format": "PhonePe PDF Statement",
            "total_count": len(raw_txs),
            "new_count": new_count,
            "duplicate_count": duplicate_count,
            "items": preview_items,
            "user_categories": categories_dict
        }

    @classmethod
    def import_transactions(
        cls,
        db: Session,
        user_id: int,
        transactions_to_import: List[Dict[str, Any]],
        filename: Optional[str] = None,
        statement_period: Optional[str] = None,
        total_found: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safely inserts user-selected statement transactions into the transactions table.
        Re-verifies duplicate uniqueness scoped to user_id.
        Records an import history entry for full auditability.
        """
        if not transactions_to_import:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No transactions were selected for import."
            )

        # Derive period if not passed
        resolved_period = statement_period
        if not resolved_period:
            dates = []
            for item in transactions_to_import:
                d = item.get("transaction_date")
                if isinstance(d, str):
                    try:
                        dates.append(datetime.strptime(parse_phonepe_date(d), "%Y-%m-%d").date())
                    except Exception:
                        pass
                elif isinstance(d, dt_date):
                    dates.append(d)
            if dates:
                dates.sort()
                min_m = dates[0].strftime("%B %Y")
                max_m = dates[-1].strftime("%B %Y")
                resolved_period = min_m if min_m == max_m else f"{dates[0].strftime('%b %Y')} – {dates[-1].strftime('%b %Y')}"
            else:
                resolved_period = datetime.now().strftime("%B %Y")

        # Refresh existing records to prevent race duplicates
        existing_txs = db.query(
            Transaction.external_transaction_id,
            Transaction.external_utr,
            Transaction.transaction_date,
            Transaction.transaction_time,
            Transaction.amount,
            Transaction.type,
            Transaction.description
        ).filter(Transaction.user_id == user_id).all()

        existing_tx_ids = {
            t.external_transaction_id.strip()
            for t in existing_txs
            if t.external_transaction_id
        }
        existing_utrs = {
            t.external_utr.strip()
            for t in existing_txs
            if t.external_utr
        }
        existing_fingerprints = {
            make_transaction_fingerprint(
                user_id=user_id,
                tx_date=str(t.transaction_date),
                tx_time=t.transaction_time,
                amount=t.amount,
                tx_type=t.type.value,
                description=t.description
            )
            for t in existing_txs
        }

        # Validate categories belonging to this user
        user_categories = {c.id: c for c in db.query(Category).filter(Category.user_id == user_id).all()}
        fallback_expense = next((c.id for c in user_categories.values() if c.type in [CategoryType.EXPENSE, CategoryType.BOTH]), None)
        fallback_income = next((c.id for c in user_categories.values() if c.type in [CategoryType.INCOME, CategoryType.BOTH]), None)

        imported_records: List[Transaction] = []
        skipped_count = 0

        for item in transactions_to_import:
            tx_id = (item.get("external_transaction_id") or "").strip()
            utr = (item.get("external_utr") or "").strip()
            tx_date_raw = item.get("transaction_date")
            tx_time_raw = item.get("transaction_time")
            amt = Decimal(str(item.get("amount")))
            tx_type_str = item.get("type", "expense").lower()
            desc = item.get("description", "").strip() or "PhonePe Transaction"

            fg = make_transaction_fingerprint(user_id, str(tx_date_raw), tx_time_raw, amt, tx_type_str, desc)

            # Deduplication check matching priority:
            # 1. Transaction ID (if present)
            # 2. UTR number (if present and tx_id missing)
            # 3. Deterministic transaction fingerprint (only when external IDs are missing)
            is_dup = False
            if tx_id:
                if tx_id in existing_tx_ids:
                    is_dup = True
            elif utr:
                if utr in existing_utrs:
                    is_dup = True
            else:
                if fg in existing_fingerprints:
                    is_dup = True

            if is_dup:
                skipped_count += 1
                continue

            # Category resolution
            cat_id = item.get("category_id")
            if not cat_id or cat_id not in user_categories:
                cat_id = fallback_expense if tx_type_str == "expense" else fallback_income

            # Parse date safely (ensuring no ValueError)
            if isinstance(tx_date_raw, str):
                norm_d = parse_phonepe_date(tx_date_raw)
                try:
                    parsed_date = datetime.strptime(norm_d, "%Y-%m-%d").date()
                except Exception:
                    parsed_date = datetime.now().date()
            elif isinstance(tx_date_raw, dt_date):
                parsed_date = tx_date_raw
            else:
                parsed_date = datetime.now().date()

            norm_time = parse_phonepe_time(tx_time_raw) if tx_time_raw else None

            new_tx = Transaction(
                user_id=user_id,
                category_id=cat_id,
                type=TransactionType.EXPENSE if tx_type_str == "expense" else TransactionType.INCOME,
                amount=amt,
                description=desc,
                transaction_date=parsed_date,
                transaction_time=norm_time,
                source="phonepe",
                external_transaction_id=tx_id or None,
                external_utr=utr or None,
                source_reference=f"PhonePe {tx_id}" if tx_id else "PhonePe Statement Import"
            )
            imported_records.append(new_tx)

            # Update in-memory sets to avoid duplicating within the same batch
            if tx_id:
                existing_tx_ids.add(tx_id)
            if utr:
                existing_utrs.add(utr)
            existing_fingerprints.add(fg)

        if imported_records:
            db.add_all(imported_records)
            db.commit()
            try:
                from app.services.scheduler_service import SchedulerService
                SchedulerService.check_budget_thresholds(db, user_id)
            except Exception:
                pass

        # Record StatementImport history entry
        calc_total_found = total_found if total_found is not None else (len(imported_records) + skipped_count)
        history_entry = StatementImport(
            user_id=user_id,
            source="phonepe",
            statement_period=resolved_period,
            filename=filename or "PhonePe_Statement.pdf",
            total_found=calc_total_found,
            total_new=len(imported_records),
            total_duplicates=skipped_count,
            total_failed=0,
            status="completed",
            error_message=None
        )
        db.add(history_entry)
        db.commit()

        logger.info(
            "Statement import completed for user_id=%d: %d inserted, %d duplicates skipped, import_id=%d",
            user_id, len(imported_records), skipped_count, history_entry.id
        )

        return {
            "imported_count": len(imported_records),
            "skipped_count": skipped_count,
            "import_id": history_entry.id,
            "statement_period": resolved_period,
            "message": f"{len(imported_records)} transactions imported successfully. {skipped_count} duplicate transactions skipped."
        }
