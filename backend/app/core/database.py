from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Engine configuration supporting both SQLite (local development/testing) and PostgreSQL
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_db_schema(bind_engine=engine) -> None:
    """Safely synchronizes table schemas across SQLite and PostgreSQL databases."""
    from sqlalchemy import text, inspect

    inspector = inspect(bind_engine)
    tables = inspector.get_table_names()
    dialect_name = bind_engine.dialect.name.lower()
    bool_def = "BOOLEAN DEFAULT FALSE" if "postgres" in dialect_name else "BOOLEAN DEFAULT 0"
    dt_type = "TIMESTAMP WITH TIME ZONE" if "postgres" in dialect_name else "DATETIME"

    columns_to_ensure = {
        "products": [
            ("subscription_enabled", bool_def),
            ("subscription_name", "VARCHAR(255)"),
            ("duration_mode", "VARCHAR(50)"),
            ("validity_value", "INTEGER"),
            ("validity_unit", "VARCHAR(50)"),
            ("billing_frequency", "VARCHAR(50) DEFAULT 'NONE'"),
            ("subscription_start_trigger", "VARCHAR(50) DEFAULT 'ORDER_ACTIVATION'"),
            ("fulfillment_type", "VARCHAR(50) DEFAULT 'PHYSICAL'"),
        ],
        "quote_lines": [
            ("subscription_enabled", bool_def),
            ("subscription_name", "VARCHAR(255)"),
            ("duration_mode", "VARCHAR(50)"),
            ("validity_value", "INTEGER"),
            ("validity_unit", "VARCHAR(50)"),
            ("billing_frequency", "VARCHAR(50) DEFAULT 'NONE'"),
            ("subscription_start_trigger", "VARCHAR(50) DEFAULT 'ORDER_ACTIVATION'"),
        ],
        "order_lines": [
            ("subscription_enabled", bool_def),
            ("subscription_name", "VARCHAR(255)"),
            ("duration_mode", "VARCHAR(50)"),
            ("validity_value", "INTEGER"),
            ("validity_unit", "VARCHAR(50)"),
            ("billing_frequency", "VARCHAR(50) DEFAULT 'NONE'"),
            ("subscription_start_trigger", "VARCHAR(50) DEFAULT 'ORDER_ACTIVATION'"),
        ],
        "subscriptions": [
            ("product_id", "INTEGER"),
            ("name", "VARCHAR(255)"),
            ("duration_mode", "VARCHAR(50)"),
            ("validity_value", "INTEGER"),
            ("validity_unit", "VARCHAR(50)"),
            ("billing_frequency", "VARCHAR(50) DEFAULT 'NONE'"),
            ("subscription_start_trigger", "VARCHAR(50) DEFAULT 'ORDER_ACTIVATION'"),
            ("start_date", dt_type),
            ("end_date", dt_type),
            ("next_billing_date", dt_type),
            ("created_at", dt_type),
        ],
        "warehouses": [
            ("created_at", dt_type),
            ("updated_at", dt_type),
        ],
        "inventories": [
            ("quantity_on_hand", "INTEGER DEFAULT 0"),
            ("quantity_allocated", "INTEGER DEFAULT 0"),
            ("updated_at", dt_type),
        ],
    }

    with bind_engine.connect() as conn:
        for table, cols in columns_to_ensure.items():
            if table in tables:
                existing_cols = {c["name"] for c in inspector.get_columns(table)}
                for col_name, col_type in cols:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception:
                            try:
                                conn.rollback()
                            except Exception:
                                pass

        if "postgres" in dialect_name and "subscriptions" in tables:
            try:
                conn.execute(text("ALTER TABLE subscriptions ALTER COLUMN plan_id DROP NOT NULL"))
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass


try:
    sync_db_schema()
except Exception:
    pass


