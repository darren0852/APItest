"""Plan/Subscription models and service."""
from database import Base, User
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta, timezone, date
import json

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    price = Column(Numeric(18, 2), nullable=False)
    duration_days = Column(Integer, default=7)
    daily_request_limit = Column(Integer, nullable=True)
    total_token_quota = Column(Integer, nullable=True)
    model_scope = Column(Text, nullable=True)  # JSON array; null = all models
    max_parallel_requests = Column(Integer, default=3)
    rpm_limit = Column(Integer, nullable=True)
    is_active = Column(Integer, default=1)

class Entitlement(Base):
    __tablename__ = "entitlements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    starts_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    remaining_tokens = Column(Integer, nullable=True)
    daily_requests_used = Column(Integer, default=0)
    daily_reset_date = Column(Date, default=lambda: date.today())
    status = Column(String, default="active")
    plan = relationship("Plan")

class PlanService:
    @staticmethod
    def purchase(db, user_id: int, plan: Plan) -> Entitlement:
        ent = Entitlement(
            user_id=user_id,
            plan_id=plan.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=plan.duration_days),
            remaining_tokens=plan.total_token_quota,
            daily_requests_used=0,
            daily_reset_date=date.today(),
            status="active",
        )
        db.add(ent)
        db.flush()
        return ent

    @staticmethod
    def get_active_entitlements(db, user_id: int):
        return db.query(Entitlement).options(relationship("Plan").and_(True)).filter(
            Entitlement.user_id == user_id,
            Entitlement.status == "active",
            Entitlement.expires_at > datetime.now(timezone.utc),
        ).all()

    @staticmethod
    def check_entitlement(db, user_id: int, model: str):
        """Returns (status, data): status = 'plan' | 'wallet' | 'reject'."""
        from sqlalchemy.orm import joinedload
        ents = db.query(Entitlement).options(joinedload(Entitlement.plan)).filter(
            Entitlement.user_id == user_id,
            Entitlement.status == "active",
            Entitlement.expires_at > datetime.now(timezone.utc),
        ).all()
        if not ents:
            return "wallet", None
        covering = None
        for ent in ents:
            scope = ent.plan.model_scope
            if scope:
                allowed = json.loads(scope)
                if model not in allowed:
                    continue
            covering = ent
            break
        if covering is None:
            return "wallet", None
        today = date.today()
        if covering.daily_reset_date != today:
            covering.daily_requests_used = 0
            covering.daily_reset_date = today
        if covering.plan.daily_request_limit is not None:
            if covering.daily_requests_used >= covering.plan.daily_request_limit:
                return "reject", "Daily request limit reached"
        if covering.remaining_tokens is not None and covering.remaining_tokens <= 0:
            return "reject", "Token quota exhausted"
        return "plan", covering

    @staticmethod
    def consume(db, ent: Entitlement, tokens_used: int):
        ent.daily_requests_used += 1
        if ent.remaining_tokens is not None:
            ent.remaining_tokens -= tokens_used
            if ent.remaining_tokens <= 0:
                ent.remaining_tokens = 0
                ent.status = "exhausted"