from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Normalize DATABASE_URL for PyMySQL driver (cloud providers frequently output 'mysql://...')
db_url = settings.DATABASE_URL
if db_url.startswith("mysql://"):
    db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

# Engine configuration with connection pooling and pre-ping to detect dropped connections
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy database session
    and guarantees closure after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_db_connection() -> bool:
    """Utility function to test database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[Database Connection Warning] Could not connect to MySQL: {e}")
        return False


def sync_database_schema():
    """Ensures all new tables and columns are created additively without data loss."""
    from app.database.base import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Check and add recurring_transaction_id column to transactions if missing
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'transactions' AND column_name = 'recurring_transaction_id'"
            ))
            exists = result.scalar()
            if not exists:
                conn.execute(text(
                    "ALTER TABLE transactions ADD COLUMN recurring_transaction_id INT NULL"
                ))
                try:
                    conn.execute(text(
                        "ALTER TABLE transactions ADD CONSTRAINT fk_transactions_recurring "
                        "FOREIGN KEY (recurring_transaction_id) REFERENCES recurring_transactions(id) ON DELETE SET NULL"
                    ))
                except Exception:
                    pass
                conn.commit()
                print("[Database Migration] Added recurring_transaction_id column to transactions table.")

            # Columns for statement import & source tracking
            new_cols = [
                ("source", "VARCHAR(50) NOT NULL DEFAULT 'manual'"),
                ("transaction_time", "VARCHAR(20) NULL"),
                ("external_transaction_id", "VARCHAR(100) NULL"),
                ("external_utr", "VARCHAR(100) NULL"),
                ("source_reference", "VARCHAR(255) NULL")
            ]
            for col_name, col_def in new_cols:
                col_res = conn.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.columns "
                    f"WHERE table_schema = DATABASE() AND table_name = 'transactions' AND column_name = '{col_name}'"
                ))
                if not col_res.scalar():
                    conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                    print(f"[Database Migration] Added {col_name} column to transactions table.")

            # Add indexes if missing
            indexes_to_add = [
                ("idx_trans_user_ext_id", "user_id, external_transaction_id"),
                ("idx_trans_user_source", "user_id, source")
            ]
            for idx_name, idx_cols in indexes_to_add:
                idx_res = conn.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.statistics "
                    f"WHERE table_schema = DATABASE() AND table_name = 'transactions' AND index_name = '{idx_name}'"
                ))
                if not idx_res.scalar():
                    try:
                        conn.execute(text(f"CREATE INDEX {idx_name} ON transactions ({idx_cols})"))
                        conn.commit()
                        print(f"[Database Migration] Created index {idx_name} on transactions.")
                    except Exception:
                        pass

            # Migration for user_preferences.monthly_summary_alerts
            pref_res = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'user_preferences' AND column_name = 'monthly_summary_alerts'"
            ))
            if not pref_res.scalar():
                conn.execute(text("ALTER TABLE user_preferences ADD COLUMN monthly_summary_alerts BOOLEAN NOT NULL DEFAULT TRUE"))
                conn.commit()
                print("[Database Migration] Added monthly_summary_alerts column to user_preferences table.")

            # Migration for notifications.type (widen to VARCHAR(50) to support new notification types)
            notif_type_res = conn.execute(text(
                "SELECT DATA_TYPE FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'notifications' AND column_name = 'type'"
            )).scalar()
            if notif_type_res and notif_type_res.lower() == 'enum':
                try:
                    conn.execute(text("ALTER TABLE notifications MODIFY COLUMN type VARCHAR(50) NOT NULL"))
                    conn.commit()
                    print("[Database Migration] Upgraded notifications.type from ENUM to VARCHAR(50).")
                except Exception as ex:
                    print(f"[Database Migration Warning] notifications.type alter: {ex}")
    except Exception as e:
        print(f"[Database Migration Warning] Error running additive migrations: {e}")

