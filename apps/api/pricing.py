"""Pricing management with versioning per the architecture doc."""
from database import Base
from sqlalchemy import Column, ForeignKey, Integer, String, Numeric, DateTime, Text
from datetime import datetime, timezone

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
