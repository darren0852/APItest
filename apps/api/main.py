from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
import asyncio
import json
import httpx, uuid, time
import os
from sqlalchemy import text
from database import get_db, init_db, SessionLocal, User, APIKey, Wallet, WalletLedger, UsageRecord
from auth import hash_password, verify_password, create_jwt, decode_jwt
from customer_keys import KEY_MANAGER
from wallet import WALLET_SERVICE, get_model_price
from plans import Plan, Entitlement, PlanService
from pricing import CustomerPrice, ModelGroup, ProviderPrice, Supplier, SupplierRoute
from admin import router as admin_router
from rate_limit import RATE_LIMITER
from supplier import get_supplier_route, upstream_request, normalize_anthropic_response
from supplier_crypto import encrypt_secret, secret_suffix

app = FastAPI(title="AI API Platform", version="0.4.0")
security = HTTPBearer(auto_error=False)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(admin_router)

LITELLM_URL = "http://localhost:4000"

class UserCreate(BaseModel):
    email: str
    password: str

class APIKeyCreate(BaseModel):
    name: str = "default"
    group_name: Optional[str] = None
    quota_limit: Optional[float] = None
    rate_limit: Optional[int] = None
    expires_at: Optional[datetime] = None

class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    group_name: Optional[str] = None
    quota_limit: Optional[float] = None
    rate_limit: Optional[int] = None
    expires_at: Optional[datetime] = None
    clear_expires_at: bool = False

class APIKeyStatusUpdate(BaseModel):
    status: str

class TopupRequest(BaseModel):
    amount: float

class PlanPurchaseRequest(BaseModel):
    plan_id: int

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list
    system: Optional[object] = None
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = SessionLocal()
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    db.close()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def validate_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> APIKey:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing API Key")
    raw_key = credentials.credentials
    if not KEY_MANAGER.validate_format(raw_key):
        raise HTTPException(status_code=401, detail="Invalid API Key format")
    key_hash = KEY_MANAGER.hash_key(raw_key)
    db = SessionLocal()
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.status == "active").first()
    db.close()
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key not found or revoked")
    if api_key.status != "active":
        raise HTTPException(status_code=403, detail="API Key disabled")
    if api_key.expires_at and api_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="API Key expired")
    if api_key.quota_limit:
        total_used = sum(item.cost for item in db.query(UsageRecord).filter(UsageRecord.api_key_id == api_key.id).all())
        if total_used >= api_key.quota_limit:
            raise HTTPException(status_code=402, detail="API Key quota limit reached")
    return api_key


def validate_api_key_raw(raw_key: str) -> APIKey:
    if not KEY_MANAGER.validate_format(raw_key):
        raise HTTPException(status_code=401, detail="Invalid API Key format")
    key_hash = KEY_MANAGER.hash_key(raw_key)
    db_v = SessionLocal()
    try:
        db_key = db_v.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        if db_key is None:
            raise HTTPException(status_code=401, detail="API Key not found or revoked")
        if db_key.status != "active":
            raise HTTPException(status_code=403, detail="API Key disabled")
        if db_key.expires_at and db_key.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="API Key expired")
        return db_key
    finally:
        db_v.close()

@app.get("/me/model-groups")
async def get_model_groups(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        groups = db.query(ModelGroup).order_by(ModelGroup.sort_order, ModelGroup.id).all()
        return [{"id": group.name, "name": group.name, "description": "选择分组后，调用时仍需输入模型 ID。"} for group in groups]
    finally:
        db.close()

def seed_plans():
    db = SessionLocal()
    try:
        if db.query(Plan).count() == 0:
            plans = [
                Plan(name="Starter", price=Decimal("10.00"), duration_days=7, daily_request_limit=50, total_token_quota=100000, max_parallel_requests=2, rpm_limit=10),
                Plan(name="Pro", price=Decimal("50.00"), duration_days=30, daily_request_limit=500, total_token_quota=2000000, max_parallel_requests=5, rpm_limit=60),
                Plan(name="Unlimited", price=Decimal("200.00"), duration_days=30, daily_request_limit=None, total_token_quota=None, max_parallel_requests=10, rpm_limit=None),
            ]
            db.add_all(plans)
            db.commit()
    finally:
        db.close()

def seed_internal_supplier():
    """Keep the local development mock route available unless an admin replaces it."""
    db = SessionLocal()
    try:
        if os.environ.get("ENABLE_INTERNAL_MOCK", "false").lower() not in ("1", "true", "yes"):
            return
        if db.query(SupplierRoute).filter(SupplierRoute.model_name == "mock-model").first():
            return
        supplier = db.query(Supplier).filter(Supplier.name == "Internal Mock Supplier").first()
        if supplier is None:
            supplier = Supplier(name="Internal Mock Supplier", status="active", priority=1, notes="Local development and integration testing route")
            db.add(supplier)
            db.flush()
        route = SupplierRoute(
            supplier_id=supplier.id,
            model_name="mock-model",
            upstream_model="mock-model",
            endpoint_url="http://localhost:9000/v1/chat/completions",
            protocol="openai",
            api_key_encrypted=encrypt_secret("mock-key-internal"),
            api_key_last4=secret_suffix("mock-key-internal"),
            status="active",
            priority=1,
        )
        db.add(route)
        db.commit()
    finally:
        db.close()

MODEL_PRICE_SEED = [
    ("glm-5.3", "Zhipu GLM", 3.000000, 10.500000, 0.000000, 0.750000),
    ("glm-5.2", "Zhipu GLM", 3.000000, 10.500000, 0.000000, 0.750000),
    ("glm-5.3-flash", "Zhipu GLM", 0.300000, 1.050000, 0.000000, 0.086250),
    ("kimi-k3.1-pro-highspeed", "Kimi", 11.700000, 61.200000, 11.700000, 0.585000),
    ("kimi-k3", "Kimi", 9.000000, 45.000000, 9.000000, 0.900000),
    ("kimi-k3.1-pro", "Kimi", 5.850000, 30.600000, 5.850000, 0.585000),
    ("kimi-k2.7-code", "Kimi", 2.437500, 10.125000, 0.000000, 0.487500),
    ("kimi-k2.6", "Kimi", 2.437500, 10.125000, 0.000000, 0.412500),
    ("MiniMax-M3", "MiniMax", 1.575000, 6.300000, 0.000000, 0.315000),
    ("MiniMax-M3.1-Flash", "MiniMax", 0.375000, 1.500000, 0.000000, 0.037500),
    ("deepseek-v4-pro:0813", "DeepSeek", 3.375000, 10.125000, 0.000000, 0.112500),
    ("deepseek-v4-pro", "DeepSeek", 3.375000, 10.125000, 0.000000, 0.112500),
    ("deepseek-v4.1-flash", "DeepSeek", 0.750000, 3.000000, 0.000000, 0.015000),
    ("deepseek-v4-flash:0731", "DeepSeek", 0.750000, 3.000000, 0.000000, 0.015000),
    ("deepseek-v4-flash", "DeepSeek", 0.750000, 3.000000, 0.000000, 0.015000),
]

OFFICIAL_PRICE_SEED = {
    "glm-5.3": (8.00, 28.00, 0.00, 2.00),
    "glm-5.2": (8.00, 28.00, 0.00, 2.00),
    "glm-5.3-flash": (0.80, 2.80, 0.00, 0.115),
    "kimi-k3.1-pro-highspeed": (26.00, 136.00, 15.60, 1.30),
    "kimi-k3": (20.00, 100.00, 12.00, 2.00),
    "kimi-k3.1-pro": (13.00, 68.00, 13.00, 1.30),
    "kimi-k2.7-code": (6.50, 27.00, 0.00, 1.30),
    "kimi-k2.6": (6.50, 27.00, 0.00, 1.10),
    "MiniMax-M3": (4.20, 16.80, 0.00, 0.84),
    "MiniMax-M3.1-Flash": (1.00, 4.00, 0.00, 0.10),
    "deepseek-v4-pro:0813": (9.00, 27.00, 0.00, 0.30),
    "deepseek-v4-pro": (9.00, 27.00, 0.00, 0.30),
    "deepseek-v4.1-flash": (2.00, 8.00, 0.00, 0.04),
    "deepseek-v4-flash:0731": (2.00, 8.00, 0.00, 0.04),
    "deepseek-v4-flash": (2.00, 8.00, 0.00, 0.04),
}

PEAK_MULTIPLIER_SEED = {
    "glm-5.3": 1.25, "glm-5.2": 1.25, "glm-5.3-flash": 1.25,
    "kimi-k3.1-pro-highspeed": 1.35, "kimi-k3": 1.35, "kimi-k3.1-pro": 1.35,
    "kimi-k2.7-code": 1.30, "kimi-k2.6": 1.30,
    "MiniMax-M3": 1.25, "MiniMax-M3.1-Flash": 1.25,
    "deepseek-v4-pro:0813": 1.30, "deepseek-v4-pro": 1.30,
    "deepseek-v4.1-flash": 1.25, "deepseek-v4-flash:0731": 1.25, "deepseek-v4-flash": 1.25,
}

def seed_model_prices():
    db = SessionLocal()
    try:
        group_names = list(dict.fromkeys(row[1] for row in MODEL_PRICE_SEED))
        for index, group_name in enumerate(group_names, 1):
            if not db.query(ModelGroup).filter(ModelGroup.name == group_name).first():
                db.add(ModelGroup(name=group_name, sort_order=index))
        for model, group_name, input_sell, output_sell, cache_write, cache_read in MODEL_PRICE_SEED:
            current = db.query(CustomerPrice).filter(CustomerPrice.model == model, CustomerPrice.is_current == 1).first()
            if current is None:
                current = CustomerPrice(
                    model=model,
                    input_sell_per_token=Decimal(str(input_sell)),
                    output_sell_per_token=Decimal(str(output_sell)),
                    cache_write_sell_per_token=Decimal(str(cache_write)),
                    cache_read_sell_per_token=Decimal(str(cache_read)),
                    group_name=group_name,
                    version=1,
                    is_current=1,
                )
                db.add(current)
            else:
                current.group_name = group_name or current.group_name
                current.cache_write_sell_per_token = Decimal(str(cache_write))
                current.cache_read_sell_per_token = Decimal(str(cache_read))
            cost = db.query(ProviderPrice).filter(ProviderPrice.model == model, ProviderPrice.is_current == 1).first()
            if cost is None:
                db.add(ProviderPrice(model=model, input_cost_per_token=Decimal("0"), output_cost_per_token=Decimal("0"), version=1, is_current=1))
        db.commit()
    finally:
        db.close()

@app.get("/public/models")
async def public_models():
    db = SessionLocal()
    try:
        groups = db.query(ModelGroup).order_by(ModelGroup.sort_order, ModelGroup.id).all()
        prices = db.query(CustomerPrice).filter(CustomerPrice.is_current == 1, CustomerPrice.group_name.isnot(None)).order_by(CustomerPrice.model).all()
        grouped = {group.name: [] for group in groups}
        for price in prices:
            if price.group_name not in grouped:
                continue
            grouped[price.group_name].append({
                "model": price.model,
                "input_sell": float(price.input_sell_per_token),
                "output_sell": float(price.output_sell_per_token),
                "cache_write_sell": float(price.cache_write_sell_per_token),
                "cache_read_sell": float(price.cache_read_sell_per_token),
                "official": ([round(value * 0.62, 2) for value in OFFICIAL_PRICE_SEED[price.model]]
                             if price.model in OFFICIAL_PRICE_SEED else None),
                "peak_multiplier": PEAK_MULTIPLIER_SEED.get(price.model, 1.0),
            })
        return [{"group_name": group.name, "models": grouped[group.name]} for group in groups]
    finally:
        db.close()

@app.get("/public/model-multiplier-history/{model}")
async def model_multiplier_history(model: str):
    base = PEAK_MULTIPLIER_SEED.get(model, 1.0)
    points = []
    day_names = ["1D", "1W"]
    spans = {"1D": 24, "1W": 7}
    for label in day_names:
        n = spans[label]
        series = []
        for i in range(n):
            hour_factor = 1.0 + 0.12 * ((i * 37) % 5) / 4
            series.append(round(base * hour_factor, 2))
        points.append({"label": label, "series": series})
    return {"model": model, "ranges": points}

@app.on_event("startup")
async def startup():
    init_db()
    seed_plans()
    seed_model_prices()
    seed_internal_supplier()

@app.get("/health")
async def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "business-backend", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)}
    finally:
        db.close()

@app.post("/auth/register")
async def register(user: UserCreate):
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if "@" not in user.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == user.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        new_user = User(email=user.email, password_hash=hash_password(user.password))
        db.add(new_user)
        db.flush()
        WALLET_SERVICE.ensure_wallet(db, new_user.id)
        db.commit()
        db.refresh(new_user)
        token = create_jwt(new_user.id, new_user.email)
        return {"message": "Registered", "user_id": new_user.id, "email": new_user.email, "token": token}
    except HTTPException:
        raise
    finally:
        db.close()

@app.post("/auth/login")
async def login(user: UserCreate):
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user is None or not verify_password(user.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if db_user.status not in ("active", "admin"):
            raise HTTPException(status_code=403, detail="Account suspended")
        token = create_jwt(db_user.id, db_user.email)
        return {"message": "Logged in", "user_id": db_user.id, "email": db_user.email, "token": token, "status": db_user.status, "is_admin": db_user.status == "admin"}
    finally:
        db.close()

@app.post("/me/api-keys")
async def create_api_key(key: APIKeyCreate, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        existing_groups = {group.name for group in db.query(ModelGroup).all()}
        if not key.group_name or key.group_name not in existing_groups:
            raise HTTPException(status_code=400, detail="请选择正确的分组")
        raw, key_hash, prefix = KEY_MANAGER.generate_raw_key()
        db_key = APIKey(
            user_id=user.id,
            key_hash=key_hash,
            prefix=prefix,
            raw_key=raw,
            name=key.name,
            group_name=key.group_name,
            quota_limit=Decimal(str(key.quota_limit)) if key.quota_limit and key.quota_limit > 0 else None,
            rate_limit=key.rate_limit if key.rate_limit and key.rate_limit > 0 else None,
            expires_at=key.expires_at,
        )
        db.add(db_key)
        db.commit()
        db.refresh(db_key)
        return {
            "key": raw,
            "id": db_key.id,
            "prefix": prefix,
            "name": key.name,
            "group_name": key.group_name,
            "created_at": db_key.created_at.isoformat(),
            "warning": "请立即保存，之后不会再显示。",
        }
    finally:
        db.close()

@app.get("/me/api-keys")
async def list_api_keys(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        keys = db.query(APIKey).filter(APIKey.user_id == user.id).order_by(APIKey.created_at.desc()).all()
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now - timedelta(days=30)
        result = []
        for k in keys:
            today_usage = db.query(UsageRecord).filter(UsageRecord.api_key_id == k.id, UsageRecord.created_at >= today_start).all()
            month_usage = db.query(UsageRecord).filter(UsageRecord.api_key_id == k.id, UsageRecord.created_at >= month_start).all()
            total_usage = db.query(UsageRecord).filter(UsageRecord.api_key_id == k.id).all()
            result.append({
                "id": k.id,
                "prefix": k.prefix,
                "raw_key": k.raw_key,
                "name": k.name,
                "group_name": k.group_name,
                "status": k.status,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat(),
                "current_concurrency": RATE_LIMITER.concurrency(k.id),
                "today": {
                    "requests": len(today_usage),
                    "input_tokens": sum(item.input_tokens for item in today_usage),
                    "output_tokens": sum(item.output_tokens for item in today_usage),
                    "cost": float(sum(item.cost for item in today_usage)),
                },
                "month": {
                    "requests": len(month_usage),
                    "input_tokens": sum(item.input_tokens for item in month_usage),
                    "output_tokens": sum(item.output_tokens for item in month_usage),
                    "cost": float(sum(item.cost for item in month_usage)),
                },
                "total": {
                    "requests": len(total_usage),
                    "input_tokens": sum(item.input_tokens for item in total_usage),
                    "output_tokens": sum(item.output_tokens for item in total_usage),
                    "cost": float(sum(item.cost for item in total_usage)),
                },
                "quota_limit": float(k.quota_limit) if k.quota_limit is not None else None,
                "rate_limit": k.rate_limit,
            })
        return result
    finally:
        db.close()

@app.put("/me/api-keys/{key_id}")
async def update_api_key(key_id: int, key: APIKeyUpdate, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        db_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == user.id).first()
        if db_key is None:
            raise HTTPException(status_code=404, detail="Key not found")
        if key.name is not None:
            db_key.name = key.name
        if key.group_name is not None:
            existing_groups = {group.name for group in db.query(ModelGroup).all()}
            if key.group_name not in existing_groups:
                raise HTTPException(status_code=400, detail="请选择正确的分组")
            db_key.group_name = key.group_name
        if key.quota_limit is not None:
            db_key.quota_limit = Decimal(str(key.quota_limit)) if key.quota_limit > 0 else None
        if key.rate_limit is not None:
            db_key.rate_limit = key.rate_limit if key.rate_limit > 0 else None
        if key.clear_expires_at:
            db_key.expires_at = None
        elif key.expires_at is not None:
            db_key.expires_at = key.expires_at
        db.commit()
        return {"message": "Key updated", "key_id": key_id}
    finally:
        db.close()

@app.post("/me/api-keys/{key_id}/status")
async def update_api_key_status(key_id: int, body: APIKeyStatusUpdate, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        db_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == user.id).first()
        if db_key is None:
            raise HTTPException(status_code=404, detail="Key not found")
        if body.status not in ("active", "paused"):
            raise HTTPException(status_code=400, detail="Invalid status")
        db_key.status = body.status
        db.commit()
        return {"message": "状态已更新", "status": body.status, "key_id": key_id}
    finally:
        db.close()

@app.delete("/me/api-keys/{key_id}")
async def revoke_api_key(key_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        db_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == user.id).first()
        if db_key is None:
            raise HTTPException(status_code=404, detail="Key not found")
        db.query(UsageRecord).filter(UsageRecord.api_key_id == key_id).update({UsageRecord.api_key_id: None})
        db.commit()
        db.delete(db_key)
        db.commit()
        return {"message": "Key deleted", "key_id": key_id}
    finally:
        db.close()

@app.get("/me/balance")
async def get_balance(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        return WALLET_SERVICE.get_balance(db, user.id)
    finally:
        db.close()

@app.post("/billing/topups")
async def topup(req: TopupRequest, user: User = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if req.amount < 1:
        raise HTTPException(status_code=400, detail="Minimum top-up is RM 1")
    amount = Decimal(str(req.amount))
    db = SessionLocal()
    try:
        result = WALLET_SERVICE.topup(db, user.id, amount)
        db.commit()
        return {"message": "Top-up successful", "amount": req.amount, "balance": result["new_balance"]}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Top-up failed")
    finally:
        db.close()

@app.get("/me/ledger")
async def get_ledger(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        entries = db.query(WalletLedger).filter(WalletLedger.user_id == user.id).order_by(WalletLedger.created_at.desc()).limit(50).all()
        return [{"id": e.id, "type": e.entry_type, "amount": float(e.amount), "balance_after": float(e.balance_after), "reference": e.reference_type, "created_at": e.created_at.isoformat()} for e in entries]
    finally:
        db.close()

@app.get("/me/usage")
async def get_usage(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        records = db.query(UsageRecord).filter(UsageRecord.user_id == user.id).order_by(UsageRecord.created_at.desc()).limit(50).all()
        return [{"id": r.id, "model": r.model, "input_tokens": r.input_tokens, "output_tokens": r.output_tokens, "cost": float(r.cost), "created_at": r.created_at.isoformat()} for r in records]
    finally:
        db.close()

@app.get("/me/dashboard")
async def get_dashboard(user: User = Depends(get_current_user), days: int = 7):
    range_days = min(max(days, 1), 90)
    sgt = timezone(timedelta(hours=8))
    now = datetime.now(sgt)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    range_start = (now - timedelta(days=range_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    def summarize(records):
        return {
            "requests": len(records),
            "input_tokens": sum(r.input_tokens for r in records),
            "output_tokens": sum(r.output_tokens for r in records),
            "cost": float(sum(r.cost for r in records)),
        }

    db = SessionLocal()
    try:
        range_records = db.query(UsageRecord).filter(UsageRecord.user_id == user.id, UsageRecord.created_at >= range_start).all()
        today_records = [record for record in range_records if record.created_at >= today_start]
        all_records = db.query(UsageRecord).filter(UsageRecord.user_id == user.id).all()
        recent_records = db.query(UsageRecord).filter(UsageRecord.user_id == user.id).order_by(UsageRecord.created_at.desc()).limit(5).all()
        wallet = WALLET_SERVICE.ensure_wallet(db, user.id)

        model_map: dict[str, list[UsageRecord]] = {}
        for record in range_records:
            model_map.setdefault(record.model, []).append(record)
        model_distribution = []
        for model, records in model_map.items():
            tokens = sum(record.input_tokens + record.output_tokens for record in records)
            model_distribution.append({
                "model": model,
                "requests": len(records),
                "tokens": tokens,
                "cost": float(sum(record.cost for record in records)),
            })
        model_distribution.sort(key=lambda item: item["tokens"], reverse=True)

        buckets: dict[str, list[UsageRecord]] = {}
        for offset in range(range_days):
            bucket_date = (now - timedelta(days=range_days - 1 - offset)).date().isoformat()
            buckets[bucket_date] = []
        for record in range_records:
            bucket_date = record.created_at.astimezone(sgt).date().isoformat()
            if bucket_date in buckets:
                buckets[bucket_date].append(record)
        trend = []
        for bucket_date, records in buckets.items():
            trend.append({
                "date": bucket_date,
                "requests": len(records),
                "input_tokens": sum(record.input_tokens for record in records),
                "output_tokens": sum(record.output_tokens for record in records),
                "cost": float(sum(record.cost for record in records)),
            })

        return {
            "range_days": range_days,
            "currency": wallet.currency,
            "balance": WALLET_SERVICE.get_balance(db, user.id),
            "today": summarize(today_records),
            "range": summarize(range_records),
            "total": summarize(all_records),
            "active_api_keys": db.query(APIKey).filter(APIKey.user_id == user.id, APIKey.status == "active").count(),
            "total_api_keys": db.query(APIKey).filter(APIKey.user_id == user.id).count(),
            "model_distribution": model_distribution,
            "trend": trend,
            "recent_usage": [{
                "id": record.id,
                "model": record.model,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "tokens": record.input_tokens + record.output_tokens,
                "cost": float(record.cost),
                "created_at": record.created_at.isoformat(),
            } for record in recent_records],
        }
    finally:
        db.close()

@app.get("/plans")
async def list_plans():
    db = SessionLocal()
    try:
        plans = db.query(Plan).filter(Plan.is_active == 1).all()
        return [{"id": p.id, "name": p.name, "price": float(p.price), "duration_days": p.duration_days, "daily_request_limit": p.daily_request_limit, "total_token_quota": p.total_token_quota, "max_parallel_requests": p.max_parallel_requests, "rpm_limit": p.rpm_limit} for p in plans]
    finally:
        db.close()

@app.post("/plans/purchase")
async def purchase_plan(req: PlanPurchaseRequest, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.id == req.plan_id, Plan.is_active == 1).first()
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        price = plan.price
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
        if wallet is None or wallet.available_balance < price:
            raise HTTPException(status_code=402, detail="Insufficient balance to purchase plan")
        wallet.available_balance -= price
        wallet.version += 1
        ledger = WalletLedger(user_id=user.id, entry_type="plan_purchase", amount=-price, currency=wallet.currency, balance_after=wallet.available_balance, reference_type="plan", reference_id=str(plan.id), idempotency_key=f"plan-{user.id}-{plan.id}-{int(time.time())}")
        db.add(ledger)
        ent = PlanService.purchase(db, user.id, plan)
        db.commit()
        return {"message": f"Plan {plan.name} activated", "entitlement_id": ent.id, "expires_at": ent.expires_at.isoformat(), "balance": float(wallet.available_balance)}
    except HTTPException:
        raise
    finally:
        db.close()

@app.get("/me/entitlement")
async def get_entitlement(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        ents = db.query(Entitlement).filter(Entitlement.user_id == user.id, Entitlement.status == "active", Entitlement.expires_at > datetime.now(timezone.utc)).all()
        return [{"id": e.id, "plan_name": e.plan.name, "expires_at": e.expires_at.isoformat(), "remaining_tokens": e.remaining_tokens, "daily_requests_used": e.daily_requests_used, "daily_request_limit": e.plan.daily_request_limit} for e in ents]
    finally:
        db.close()

@app.post("/v1/chat/completions")
async def proxy_chat_completions(req: ChatCompletionRequest, api_key: APIKey = Depends(validate_api_key)):
    price_db = SessionLocal()
    try:
        price = get_model_price(price_db, req.model)
    finally:
        price_db.close()
    if price is None:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
    if price.get("group") != api_key.group_name:
        raise HTTPException(status_code=403, detail="该模型不属于当前密钥分组")
    estimated_input = sum(len(str(m.get("content", ""))) for m in req.messages) // 4 + 1
    estimated_output = 256
    estimated_cost = (estimated_input * price["input"] + estimated_output * price["output"]) / Decimal("1000000")
    estimated_cost = max(estimated_cost, Decimal("0.01"))
    rate_limit = api_key.rate_limit or 60
    rl_ok, remaining = RATE_LIMITER.check(f"rl:{api_key.id}", rate_limit, 60)
    if not rl_ok:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {rate_limit} requests/minute")
    request_id = str(uuid.uuid4())
    use_plan = False
    db = SessionLocal()
    try:
        supplier_route = get_supplier_route(db, req.model)
        if supplier_route is None:
            raise HTTPException(status_code=404, detail=f"No active supplier route for model: {req.model}")
        if api_key.group_name == "openai" and supplier_route.protocol != "openai":
            raise HTTPException(status_code=403, detail="当前分组不支持该模型协议")
        if api_key.group_name == "anthropic" and supplier_route.protocol != "anthropic":
            raise HTTPException(status_code=403, detail="当前分组不支持该模型协议")
        supplier_route_id = int(supplier_route.id)
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if user is None or user.status not in ("active", "admin"):
            raise HTTPException(status_code=403, detail="Account suspended")
        ent_result = PlanService.check_entitlement(db, user.id, req.model)
        if ent_result[0] == "plan":
            active_entitlement = ent_result[1]
            entitlement_id = int(active_entitlement.id)
            use_plan = True
        elif ent_result[0] == "reject":
            raise HTTPException(status_code=402, detail=ent_result[1])
        else:
            use_plan = False
            if not WALLET_SERVICE.check_balance(db, user.id, estimated_cost):
                raise HTTPException(status_code=402, detail="Insufficient balance. Please top up.")
            WALLET_SERVICE.reserve(db, user.id, estimated_cost)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Billing error: {str(e)}")
    finally:
        db.close()
    route_db = SessionLocal()
    try:
        current_supplier_route = route_db.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
        if current_supplier_route is None:
            raise HTTPException(status_code=404, detail="Supplier route disappeared")
        system_text = str(req.system or "")
        messages_for_supplier = []
        if system_text:
            messages_for_supplier.append({"role": "system", "content": system_text})
        for item in req.messages:
            role = item.get("role") if isinstance(item, dict) else "user"
            content = item.get("content", "") if isinstance(item, dict) else ""
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(str(block.get("text", "")))
                        elif block_type == "tool_result":
                            nested = block.get("content", "")
                            text_parts.append(str(nested) if isinstance(nested, str) else json.dumps(nested, ensure_ascii=False))
                        elif block_type == "tool_use":
                            text_parts.append(json.dumps({"name": block.get("name"), "input": block.get("input", {})}, ensure_ascii=False))
                content = "\n".join(text_parts)
            messages_for_supplier.append({"role": "assistant" if role == "assistant" else "user", "content": str(content)})
        endpoint_url, upstream_headers, upstream_body = upstream_request(current_supplier_route, messages_for_supplier, req.stream == True)
        upstream_body["max_tokens"] = req.max_tokens or 4096
        if current_supplier_route.protocol == "anthropic" and system_text:
            upstream_body["system"] = system_text
    finally:
        route_db.close()
    RATE_LIMITER.increment_concurrency(api_key.id)
    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: httpx.post(endpoint_url, headers=upstream_headers, json=upstream_body, timeout=60.0)
            ),
            timeout=75.0,
        )
    except asyncio.TimeoutError:
        resp = None
        raise HTTPException(status_code=504, detail="Supplier timeout")
    if isinstance(resp, httpx.Response) and resp.status_code != 200:
        error_detail = f"Supplier error: {resp.text}"
        db_error = SessionLocal()
        try:
            route_error = db_error.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
            if route_error:
                route_error.key_status = "error"
                route_error.last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                db_error.commit()
        finally:
            db_error.close()
        db_fail = SessionLocal()
        try:
            if not use_plan:
                WALLET_SERVICE.settle(db_fail, api_key.user_id, request_id, estimated_cost, Decimal("0"))
            db_fail.commit()
        finally:
            db_fail.close()
        RATE_LIMITER.decrement_concurrency(api_key.id)
        raise HTTPException(status_code=resp.status_code, detail=error_detail)
    if not isinstance(resp, httpx.Response):
        RATE_LIMITER.decrement_concurrency(api_key.id)
        raise HTTPException(status_code=502, detail="Supplier unreachable")
    result = resp.json()
    if current_supplier_route.protocol == "anthropic":
        result = normalize_anthropic_response(req.model, result)
    else:
        result["model"] = req.model
    db_success = SessionLocal()
    try:
        route_success = db_success.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
        if route_success:
            route_success.key_status = "healthy"
            route_success.last_error = None
            db_success.commit()
    finally:
        db_success.close()
    RATE_LIMITER.decrement_concurrency(api_key.id)
    usage = result.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = input_tokens + output_tokens
    usage_details = usage.get("prompt_tokens_details") or {}
    cached_tokens = usage_details.get("cached_tokens", 0) or 0
    cache_creation_tokens = (
        usage.get("cache_creation_input_tokens", 0)
        or usage_details.get("cache_creation_input_tokens", 0)
        or 0
    )
    cache_read_price = price.get("cache_read", Decimal("0"))
    cache_write_price = price.get("cache_write", Decimal("0"))
    uncached_input = max(input_tokens - cached_tokens - cache_creation_tokens, 0)
    actual_cost = (
        uncached_input * price["input"]
        + cached_tokens * cache_read_price
        + cache_creation_tokens * cache_write_price
        + output_tokens * price["output"]
    ) / Decimal("1000000")
    db3 = SessionLocal()
    try:
        if use_plan:
            db3_ent = db3.query(Entitlement).filter(Entitlement.id == entitlement_id).first()
            if db3_ent:
                PlanService.consume(db3, db3_ent, total_tokens)
        else:
            WALLET_SERVICE.settle(db3, api_key.user_id, request_id, estimated_cost, actual_cost)
        WALLET_SERVICE.record_usage(
            db3,
            api_key.user_id,
            api_key.id,
            req.model,
            input_tokens,
            output_tokens,
            actual_cost,
            cache_read_tokens=cached_tokens,
            cache_write_tokens=cache_creation_tokens,
        )
        db3.commit()
    except Exception:
        db3.rollback()
    finally:
        db3.close()
    result["request_id"] = request_id
    return result

@app.post("/v1/messages")
async def proxy_messages(request: Request, req: ChatCompletionRequest):
    api_key = await _resolve_api_key(request)
    price_db = SessionLocal()
    try:
        price = get_model_price(price_db, req.model)
    finally:
        price_db.close()
    if price is None:
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
    if price.get("group") != api_key.group_name:
        raise HTTPException(status_code=403, detail="该模型不属于当前密钥分组")
    estimated_input = sum(len(str(m.get("content", ""))) for m in req.messages) // 4 + 1
    estimated_output = 256
    estimated_cost = (estimated_input * price["input"] + estimated_output * price["output"]) / Decimal("1000000")
    estimated_cost = max(estimated_cost, Decimal("0.01"))
    rate_limit = api_key.rate_limit or 60
    rl_ok, remaining = RATE_LIMITER.check(f"rl:{api_key.id}", rate_limit, 60)
    if not rl_ok:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {rate_limit} requests/minute")
    request_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        supplier_route = get_supplier_route(db, req.model)
        if supplier_route is None:
            raise HTTPException(status_code=404, detail=f"No active supplier route for model: {req.model}")
        supplier_route_id = int(supplier_route.id)
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if user is None or user.status not in ("active", "admin"):
            raise HTTPException(status_code=403, detail="Account suspended")
        ent_result = PlanService.check_entitlement(db, user.id, req.model)
        if ent_result[0] == "plan":
            use_plan = True
        elif ent_result[0] == "reject":
            raise HTTPException(status_code=402, detail=ent_result[1])
        else:
            if not WALLET_SERVICE.check_balance(db, user.id, estimated_cost):
                raise HTTPException(status_code=402, detail="Insufficient balance. Please top up.")
            WALLET_SERVICE.reserve(db, user.id, estimated_cost)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Billing error: {str(e)}")
    finally:
        db.close()
    route_db = SessionLocal()
    try:
        current_supplier_route = route_db.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
        if current_supplier_route is None:
            raise HTTPException(status_code=404, detail="Supplier route disappeared")
        if isinstance(req.system, list):
            system_text = "\n".join(
                str(block.get("text", "")) if isinstance(block, dict) and block.get("type") == "text" else str(block)
                for block in req.system
            )
        elif req.system is None:
            system_text = ""
        else:
            system_text = str(req.system)
        messages_for_supplier = []
        if system_text:
            messages_for_supplier.append({"role": "system", "content": system_text})
        for item in req.messages:
            role = item.get("role") if isinstance(item, dict) else "user"
            content = item.get("content", "") if isinstance(item, dict) else ""
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(str(block.get("text", "")))
                        elif block_type == "tool_result":
                            nested = block.get("content", "")
                            text_parts.append(str(nested) if isinstance(nested, str) else json.dumps(nested, ensure_ascii=False))
                        elif block_type == "tool_use":
                            text_parts.append(json.dumps({"name": block.get("name"), "input": block.get("input", {})}, ensure_ascii=False))
                content = "\n".join(text_parts)
            messages_for_supplier.append({"role": "assistant" if role == "assistant" else "user", "content": str(content)})
        endpoint_url, upstream_headers, upstream_body = upstream_request(current_supplier_route, messages_for_supplier, req.stream == True)
        upstream_body["max_tokens"] = req.max_tokens or 4096
        if current_supplier_route.protocol == "anthropic" and system_text:
            upstream_body["system"] = system_text
    finally:
        route_db.close()
    if "max_tokens" not in json.loads(json.dumps(upstream_body)):
        upstream_body["max_tokens"] = 4096
    if req.stream:
        def anthropic_stream():
            text_parts = []
            stream_usage = {}
            try:
                with httpx.stream(
                    "POST",
                    endpoint_url,
                    headers=upstream_headers,
                    json=upstream_body,
                    timeout=90.0,
                ) as resp:
                    if resp.status_code != 200:
                        detail = resp.read().decode("utf-8", "ignore")[:500]
                        payload = json.dumps({"type":"error","error":{"type":"supplier_error","message":detail}}, ensure_ascii=False)
                        yield f"event: error\ndata: {payload}\n\n".encode("utf-8")
                        WALLET_SERVICE.settle(SessionLocal(), api_key.user_id, request_id, estimated_cost, Decimal("0"))
                        return
                    yield (
                        "event: message_start\ndata: " + json.dumps({
                            "type": "message_start",
                            "message": {
                                "id": f"msg_{request_id}",
                                "type": "message",
                                "role": "assistant",
                                "model": req.model,
                                "content": [],
                                "stop_reason": None,
                                "stop_sequence": None,
                                "usage": {"input_tokens": estimated_input, "output_tokens": 0},
                            },
                        }, ensure_ascii=False) + "\n\n"
                    ).encode("utf-8")
                    yield (
                        "event: content_block_start\ndata: " + json.dumps({
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        }) + "\n\n"
                    ).encode("utf-8")
                    for raw_line in resp.iter_lines():
                        line = raw_line.decode("utf-8", "ignore") if isinstance(raw_line, bytes) else raw_line
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except Exception:
                            continue
                        if chunk.get("usage"):
                            stream_usage = chunk["usage"]
                        delta = ((chunk.get("choices") or [{}])[0]).get("delta", {})
                        piece = delta.get("content") or ""
                        if not piece:
                            continue
                        text_parts.append(str(piece))
                        yield (
                            "event: content_block_delta\ndata: " + json.dumps({
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {"type": "text_delta", "text": piece},
                            }, ensure_ascii=False) + "\n\n"
                        ).encode("utf-8")
                    yield (
                        "event: content_block_stop\ndata: " + json.dumps({
                            "type": "content_block_stop",
                            "index": 0,
                        }) + "\n\n"
                    ).encode("utf-8")
                    output_tokens = stream_usage.get("completion_tokens") or max(len("".join(text_parts)) // 4, 1)
                    yield (
                        "event: message_delta\ndata: " + json.dumps({
                            "type": "message_delta",
                            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": output_tokens},
                        }, ensure_ascii=False) + "\n\n"
                    ).encode("utf-8")
                    yield "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n".encode("utf-8")
                    input_tokens = stream_usage.get("prompt_tokens") or estimated_input
                    prompt_details = stream_usage.get("prompt_tokens_details") or {}
                    cached_tokens = prompt_details.get("cached_tokens") or 0
                    cache_creation_tokens = prompt_details.get("cache_creation_input_tokens") or 0
                    uncached_input = max(input_tokens - cached_tokens - cache_creation_tokens, 0)
                    actual_cost = (
                        uncached_input * price["input"]
                        + cached_tokens * price.get("cache_read", Decimal("0"))
                        + cache_creation_tokens * price.get("cache_write", Decimal("0"))
                        + output_tokens * price["output"]
                    ) / Decimal("1000000")
                    db3 = SessionLocal()
                    try:
                        WALLET_SERVICE.settle(db3, api_key.user_id, request_id, estimated_cost, actual_cost)
                        route_db3 = db3.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
                        if route_db3:
                            route_db3.key_status = "healthy"
                            route_db3.last_error = None
                        db3.commit()
                    finally:
                        db3.close()
            except Exception as exc:
                if not text_parts:
                    payload = json.dumps({"type":"error","error":{"type":"supplier_error","message":str(exc)}}, ensure_ascii=False)
                    yield f"event: error\ndata: {payload}\n\n".encode("utf-8")
                WALLET_SERVICE.settle(SessionLocal(), api_key.user_id, request_id, estimated_cost, Decimal("0"))
            finally:
                RATE_LIMITER.decrement_concurrency(api_key.id)
        return StreamingResponse(
            anthropic_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "close",
                "X-Accel-Buffering": "no",
            },
        )
    RATE_LIMITER.increment_concurrency(api_key.id)
    try:
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: httpx.post(endpoint_url, headers=upstream_headers, json=upstream_body, timeout=60.0)
                ),
                timeout=75.0,
            )
        except Exception:
            WALLET_SERVICE.settle(SessionLocal(), api_key.user_id, request_id, estimated_cost, Decimal("0"))
            raise HTTPException(status_code=504, detail="Supplier timeout")
    finally:
        pass
    if resp.status_code != 200:
        db_error = SessionLocal()
        try:
            route_error = db_error.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
            if route_error:
                route_error.key_status = "error"
                route_error.last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                db_error.commit()
        finally:
            db_error.close()
        WALLET_SERVICE.settle(SessionLocal(), api_key.user_id, request_id, estimated_cost, Decimal("0"))
        RATE_LIMITER.decrement_concurrency(api_key.id)
        raise HTTPException(status_code=resp.status_code, detail=f"Supplier error: {resp.text}")
    result = resp.json()
    # Convert OpenAI-shaped response to Anthropic /v1/messages format for Claude Code compatibility
    if "choices" in result and "content" not in result:
        choice0 = (result.get("choices") or [{}])[0]
        msg0 = choice0.get("message", {})
        openai_usage = result.get("usage", {})
        result = {
            "id": result.get("id") or "msg_" + str(uuid.uuid4()),
            "type": "message",
            "role": "assistant",
            "model": req.model,
            "content": [{"type": "text", "text": msg0.get("content", "")}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": openai_usage.get("prompt_tokens", 0),
                "output_tokens": openai_usage.get("completion_tokens", 0),
                "cache_read_input_tokens": (openai_usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                "cache_creation_input_tokens": (openai_usage.get("prompt_tokens_details") or {}).get("cache_creation_input_tokens", 0) or 0,
            },
        }
    db_success = SessionLocal()
    try:
        route_success = db_success.query(SupplierRoute).filter(SupplierRoute.id == supplier_route_id).first()
        if route_success:
            route_success.key_status = "healthy"
            route_success.last_error = None
            db_success.commit()
    finally:
        db_success.close()
    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = input_tokens + output_tokens
    cached_tokens = usage.get("cache_read_input_tokens", 0) or 0
    cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0
    uncached_input = max(input_tokens - cached_tokens - cache_creation_tokens, 0)
    actual_cost = (
        uncached_input * price["input"]
        + cached_tokens * price.get("cache_read", Decimal("0"))
        + cache_creation_tokens * price.get("cache_write", Decimal("0"))
        + output_tokens * price["output"]
    ) / Decimal("1000000")
    db3 = SessionLocal()
    try:
        WALLET_SERVICE.settle(db3, api_key.user_id, request_id, estimated_cost, actual_cost)
        db3.commit()
    finally:
        db3.close()
    RATE_LIMITER.decrement_concurrency(api_key.id)
    result["model"] = req.model
    return result

async def _resolve_api_key(request: Request) -> APIKey:
    auth = request.headers.get("authorization") or ""
    xkey = request.headers.get("x-api-key") or ""
    if auth.lower().startswith("bearer "):
        raw = auth.split(" ", 1)[1].strip()
    elif xkey:
        raw = xkey.strip()
    else:
        raise HTTPException(status_code=401, detail="Missing API Key")
    return validate_api_key_raw(raw)
