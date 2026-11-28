"""Pricing management with versioning per the architecture doc."""
from database import Base, SessionLocal
from sqlalchemy import Column, ForeignKey, Integer, String, Numeric, DateTime, Text
from datetime import datetime, timezone, timedelta
import hashlib
import json

class ProviderPrice(Base):
    """Upstream cost price per model, versioned."""
    __tablename__ = "provider_prices"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, nullable=False, index=True)
    input_cost_per_token = Column(Numeric(18, 10), nullable=False)
    output_cost_per_token = Column(Numeric(18, 10), nullable=False)
    cache_write_cost_per_token = Column(Numeric(18, 10), nullable=False, default=0)
    cache_read_cost_per_token = Column(Numeric(18, 10), nullable=False, default=0)
    currency = Column(String(3), default="CNY")
    version = Column(Integer, default=1)
    effective_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_current = Column(Integer, default=1)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CustomerPrice(Base):
    """Customer sell price per model, versioned."""
    __tablename__ = "customer_prices"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, nullable=False, index=True)
    input_sell_per_token = Column(Numeric(18, 10), nullable=False)
    output_sell_per_token = Column(Numeric(18, 10), nullable=False)
    cache_write_sell_per_token = Column(Numeric(18, 10), nullable=False, default=0)
    cache_read_sell_per_token = Column(Numeric(18, 10), nullable=False, default=0)
    group_name = Column(String, nullable=True, index=True)
    currency = Column(String(3), default="MYR")
    version = Column(Integer, default=1)
    effective_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_current = Column(Integer, default=1)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ModelGroup(Base):
    """Admin-defined model grouping for keys, pricing, and model plaza."""
    __tablename__ = "model_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    sort_order = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ModelMultiplier(Base):
    """Admin-controlled real billing multiplier curve for all model charges."""
    __tablename__ = "model_multipliers"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, unique=True, nullable=False, index=True)
    hourly_multipliers = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class DailyMultiplier(Base):
    """One billing multiplier curve per model + Malaysia/Singapore date."""
    __tablename__ = "daily_multipliers"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, nullable=False, index=True)
    business_date = Column(String(10), nullable=False, index=True)
    hourly_multipliers = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

DEFAULT_HOURLY_MULTIPLIERS = [
    1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
    1.05, 1.10, 1.15, 1.18, 1.20, 1.22,
    1.25, 1.22, 1.18, 1.20, 1.22, 1.25,
    1.28, 1.32, 1.28, 1.22, 1.15, 1.08,
]

def parse_hourly_multipliers(raw: str | None) -> list[float]:
    try:
        result = [float(item) for item in json.loads(raw or "[]")]
    except Exception:
        result = []
    if len(result) != 24:
        result = DEFAULT_HOURLY_MULTIPLIERS[:]
    return [round(value, 4) for value in result]


AUTO_MULTIPLIER_BASE = [
    1.80, 1.71, 1.62,
    1.20, 1.20, 1.20,
    1.26, 1.34, 1.42, 1.48,
    1.50, 1.54, 1.58, 1.56, 1.60, 1.64, 1.68, 1.70, 1.72, 1.74,
    1.90, 2.00, 1.90, 1.74,
]
AUTO_MULTIPLIER_MIN = 1.20
AUTO_MULTIPLIER_MAX = 2.20
AUTO_MULTIPLIER_K3_MIN = 1.30
AUTO_MULTIPLIER_LOW_HOURS = {3, 4, 5}


def local_business_date() -> str:
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def _stable_ratio(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)

class Provider(Base):
    """Upstream model provider registry."""
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    api_base_url = Column(String, nullable=True)
    status = Column(String, default="active")  # active / disabled
    priority = Column(Integer, default=1)
    key_status = Column(String, default="unknown")  # unknown / healthy / error
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Supplier(Base):
    """Supplier account that can own one or more upstream model routes."""
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="active")
    priority = Column(Integer, default=1)
    contact_email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class SupplierRoute(Base):
    """Encrypted upstream credential and endpoint for one platform model."""
    __tablename__ = "supplier_routes"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    model_name = Column(String, unique=True, nullable=False, index=True)
    upstream_model = Column(String, nullable=False)
    endpoint_url = Column(String, nullable=False)
    protocol = Column(String, default="openai")  # openai / anthropic
    api_key_encrypted = Column(Text, nullable=False)
    api_key_last4 = Column(String(4), nullable=False)
    status = Column(String, default="active")
    priority = Column(Integer, default=1)
    key_status = Column(String, default="unknown")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    """Immutable audit trail for admin actions."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    detail = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
def _model_offset(model: str) -> float:
    value = _stable_ratio(f"model:{model}") * 0.16 - 0.08
    return round(value, 4)


def _day_offset(model: str, business_date: str) -> float:
    value = _stable_ratio(f"day:{model}:{business_date}") * 0.10 - 0.05
    return round(value, 4)


def generate_auto_hourly_multipliers(model: str, business_date: str) -> list[float]:
    model_offset = _model_offset(model)
    day_offset = _day_offset(model, business_date)
    is_k3 = model.lower().startswith("kimi-k3")

    values = []
    for hour, base_value in enumerate(AUTO_MULTIPLIER_BASE):
        if hour in AUTO_MULTIPLIER_LOW_HOURS:
            value = 1.20 + max(0.0, model_offset * 0.35)
            value += (_stable_ratio(f"low:{model}:{business_date}:{hour}") - 0.5) * 0.04
            if is_k3:
                value = 1.30
        else:
            hour_offset = (_stable_ratio(f"hour:{model}:{business_date}:{hour}") - 0.5) * 0.06
            value = base_value + model_offset + day_offset + hour_offset

        value = round(min(AUTO_MULTIPLIER_MAX, max(AUTO_MULTIPLIER_MIN, value)), 2)
        if is_k3:
            value = round(max(AUTO_MULTIPLIER_K3_MIN, value), 2)
        values.append(value)
    return values


def ensure_daily_multiplier(db, model: str, business_date: str | None = None):
    business_date = business_date or local_business_date()
    separate_db = SessionLocal()
    try:
        row = separate_db.query(DailyMultiplier).filter(
            DailyMultiplier.model == model,
            DailyMultiplier.business_date == business_date,
        ).first()
        if row is None:
            curve = generate_auto_hourly_multipliers(model, business_date)
            row = DailyMultiplier(
                model=model,
                business_date=business_date,
                hourly_multipliers=json.dumps(curve),
            )
            separate_db.add(row)
            separate_db.commit()
        return parse_hourly_multipliers(row.hourly_multipliers)
    finally:
        separate_db.close()


def ensure_daily_multipliers_for_days(db, days: int = 7):
    base_date = datetime.now(timezone(timedelta(hours=8))).date()
    models = [row.model for row in db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).all()]
    for day_offset in range(days + 1):
        business_date = (base_date + timedelta(days=day_offset)).isoformat()
        for model in models:
            ensure_daily_multiplier(db, model, business_date)
    db.commit()
