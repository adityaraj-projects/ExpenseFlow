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
    except Exception as e:
        print(f"[Database Migration Warning] Error running additive migrations: {e}")

