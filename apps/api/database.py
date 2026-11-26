"""Database models and connection."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timezone
import os

DB_USER = os.environ.get("DB_USER", "apidev")
DB_PASS = os.environ.get("DB_PASS", "apidev123")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "apiplatform")
DATABASE_URL = os.environ.get("DATABASE_URL") or f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    status = Column(String, default="active")
    risk_flag = Column(Boolean, default=False)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    api_keys = relationship("APIKey", back_populates="user")

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String, unique=True, nullable=False, index=True)
    prefix = Column(String, nullable=False)
    raw_key = Column(String, nullable=True)  # TEST ONLY: store plaintext for easy copying, remove before production
    name = Column(String, default="default")
    status = Column(String, default="active")
    group_name = Column(String, nullable=True)
    quota_limit = Column(Numeric(18, 2), nullable=True)
    rate_limit = Column(Integer, nullable=True)
    concurrency_limit = Column(Integer, nullable=False, default=5)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="api_keys")

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    currency = Column(String(3), default="MYR")
    available_balance = Column(Numeric(18, 8), default=0)
    reserved_balance = Column(Numeric(18, 8), default=0)
    version = Column(Integer, default=0)
    user = relationship("User")

class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_type = Column(String, nullable=False)
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(3), default="MYR")
    balance_after = Column(Numeric(18, 8), nullable=False)
    reference_type = Column(String, nullable=True)
    reference_id = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    api_key_id = Column(Integer, ForeignKey("api_keys.id"))
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    cost = Column(Numeric(18, 8), default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS group_name VARCHAR"))
        connection.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS quota_limit NUMERIC(18, 2)"))
        connection.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS rate_limit INTEGER"))
        connection.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS concurrency_limit INTEGER NOT NULL DEFAULT 5"))
        connection.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
        connection.execute(text("ALTER TABLE customer_prices ADD COLUMN IF NOT EXISTS cache_write_sell_per_token NUMERIC(18, 10) DEFAULT 0"))
        connection.execute(text("ALTER TABLE customer_prices ADD COLUMN IF NOT EXISTS cache_read_sell_per_token NUMERIC(18, 10) DEFAULT 0"))
        connection.execute(text("ALTER TABLE customer_prices ADD COLUMN IF NOT EXISTS group_name VARCHAR"))
        connection.execute(text("ALTER TABLE usage_records ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER DEFAULT 0"))
        connection.execute(text("ALTER TABLE usage_records ADD COLUMN IF NOT EXISTS cache_write_tokens INTEGER DEFAULT 0"))
        connection.execute(text("ALTER TABLE provider_prices ADD COLUMN IF NOT EXISTS cache_write_cost_per_token NUMERIC(18, 10) DEFAULT 0"))
        connection.execute(text("ALTER TABLE provider_prices ADD COLUMN IF NOT EXISTS cache_read_cost_per_token NUMERIC(18, 10) DEFAULT 0"))
        connection.execute(text("UPDATE provider_prices SET currency = 'CNY' WHERE currency = 'USD'"))
        connection.execute(text("ALTER TABLE wallets ALTER COLUMN available_balance TYPE NUMERIC(18, 8)"))
        connection.execute(text("ALTER TABLE wallets ALTER COLUMN reserved_balance TYPE NUMERIC(18, 8)"))
        connection.execute(text("ALTER TABLE wallet_ledger ALTER COLUMN amount TYPE NUMERIC(18, 8)"))
        connection.execute(text("ALTER TABLE wallet_ledger ALTER COLUMN balance_after TYPE NUMERIC(18, 8)"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
