"""Admin panel endpoints - full management per architecture doc Section 8.1."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, User, APIKey, Wallet, WalletLedger, UsageRecord
from plans import Entitlement
from pricing import ProviderPrice, CustomerPrice, DailyMultiplier, ModelGroup, ModelMultiplier, Provider, Supplier, SupplierRoute, AuditLog, parse_hourly_multipliers
from auth import decode_jwt
from customer_keys import KEY_MANAGER
from wallet import WALLET_SERVICE
from supplier_crypto import encrypt_secret, secret_suffix
from decimal import Decimal
import json
from datetime import datetime, timezone
from sqlalchemy import text

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer(auto_error=False)

class BalanceAdjust(BaseModel):
    user_id: int
    amount: float
    reason: str

class UserSuspend(BaseModel):
    reason: str

class RiskFlag(BaseModel):
    flagged: bool
    reason: str

class PriceUpdate(BaseModel):
    model: str
    input_cost_per_token: float
    output_cost_per_token: float
    input_sell_per_token: float
    output_sell_per_token: float
    cache_write_sell_per_token: Optional[float] = 0
    cache_read_sell_per_token: Optional[float] = 0
    cache_write_cost_per_token: Optional[float] = 0
    cache_read_cost_per_token: Optional[float] = 0
    group_name: Optional[str] = None

class HourlyMultipliersUpdate(BaseModel):
    model: str
    hourly_multipliers: list[float]

class DailyMultipliersUpdate(BaseModel):
    model: str
    business_date: str
    hourly_multipliers: list[float]

class PricingGroupCreate(BaseModel):
    name: str

class ProviderUpdate(BaseModel):
    name: str
    api_base_url: Optional[str] = None
    status: str = "active"
    priority: int = 1

class SupplierCreate(BaseModel):
    name: str
    status: str = "active"
    priority: int = 1
    contact_email: Optional[str] = None
    notes: Optional[str] = None

class SupplierRouteCreate(BaseModel):
    model_name: str
    model_config = {"protected_namespaces": ()}
    upstream_model: str
    endpoint_url: str
    api_key: str
    priority: int = 1

class SupplierRouteUpdate(BaseModel):
    upstream_model: str
    endpoint_url: str
    api_key: Optional[str] = None

def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = SessionLocal()
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    db.close()
    if user is None or user.status != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def audit_log(db, admin_id: int, action: str, target_type: str = None, target_id: str = None, detail: str = None):
    entry = AuditLog(admin_id=admin_id, action=action, target_type=target_type, target_id=target_id, detail=detail)
    db.add(entry)

def _wallet_summary(db):
    from sqlalchemy import func

    customer_wallets = (
        db.query(Wallet)
        .join(User, Wallet.user_id == User.id)
        .filter(User.status != "admin")
        .all()
    )
    admin_wallet = (
        db.query(Wallet)
        .join(User, Wallet.user_id == User.id)
        .filter(User.email == "ngdarren0852@gmail.com")
        .first()
    )
    customer_usage = (
        db.query(func.coalesce(func.sum(WalletLedger.amount), 0))
        .join(User, User.id == WalletLedger.user_id)
        .filter(WalletLedger.entry_type == "usage", User.status != "admin")
        .scalar()
    )
    return (
        sum((wallet.available_balance or 0) for wallet in customer_wallets),
        admin_wallet.available_balance or 0 if admin_wallet else 0,
        customer_usage or 0,
    )


def _supplier_cost_cny(db):
    from decimal import Decimal
    from sqlalchemy import func

    price_map = {
        row.model: row
        for row in db.query(ProviderPrice).filter(ProviderPrice.is_current == 1).all()
    }
    usage_rows = (
        db.query(
            UsageRecord.model,
            func.sum(UsageRecord.input_tokens),
            func.sum(UsageRecord.output_tokens),
            func.sum(UsageRecord.cache_write_tokens),
            func.sum(UsageRecord.cache_read_tokens),
        )
        .group_by(UsageRecord.model)
        .all()
    )
    total = Decimal("0")
    for model, input_tokens, output_tokens, cache_write, cache_read in usage_rows:
        price = price_map.get(model)
        if price is None:
            continue
        total += (
            max((input_tokens or 0) - (cache_read or 0) - (cache_write or 0), 0) * price.input_cost_per_token
            + (output_tokens or 0) * price.output_cost_per_token
            + (cache_write or 0) * price.cache_write_cost_per_token
            + (cache_read or 0) * price.cache_read_cost_per_token
        ) / Decimal("1000000")
    return total


def _customer_wallet_summary(db):
    customer_wallets = (
        db.query(Wallet)
        .join(User, Wallet.user_id == User.id)
        .filter(User.status != "admin")
        .all()
    )
    admin_wallet = (
        db.query(Wallet)
        .join(User, Wallet.user_id == User.id)
        .filter(User.email == "ngdarren0852@gmail.com")
        .first()
    )
    return (
        sum((wallet.available_balance or 0) for wallet in customer_wallets),
        admin_wallet.available_balance or 0 if admin_wallet else 0,
    )


@router.get("/stats")

async def get_stats(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        total_users = db.query(User).filter(User.status != "admin").count()
        active_users = db.query(User).filter(User.status == "active").count()
        suspended_users = db.query(User).filter(User.status == "suspended").count()
        flagged_users = db.query(User).filter(User.risk_flag == True).count()
        total_keys = db.query(APIKey).filter(APIKey.status == "active").count()
        total_usage = db.query(UsageRecord).count()
        total_input_tokens = db.query(UsageRecord).with_entities(UsageRecord.input_tokens).all()
        total_output_tokens = db.query(UsageRecord).with_entities(UsageRecord.output_tokens).all()
        tin = sum(t[0] for t in total_input_tokens) if total_input_tokens else 0
        tout = sum(t[0] for t in total_output_tokens) if total_output_tokens else 0
        total_cost_rows = db.query(UsageRecord).with_entities(UsageRecord.cost).all()
        tcost = sum(c[0] for c in total_cost_rows) if total_cost_rows else 0
        wallet_rows = db.query(Wallet).with_entities(Wallet.available_balance).all()
        total_wallet = sum(w[0] for w in wallet_rows) if wallet_rows else 0
        active_plans = db.query(Entitlement).filter(Entitlement.status == "active", Entitlement.expires_at > datetime.now(timezone.utc)).count()
        return {"total_users": total_users, "active_users": active_users, "suspended_users": suspended_users, "flagged_users": flagged_users, "active_api_keys": total_keys, "total_api_requests": total_usage, "total_input_tokens": tin, "total_output_tokens": tout, "total_cost": float(tcost), "total_wallet_balance": float(total_wallet), "active_plans": active_plans}
    finally:
        db.close()

@router.get("/users")
async def list_users(admin: User = Depends(require_admin), search: str = None, status: str = None, flagged: str = None):
    db = SessionLocal()
    try:
        q = db.query(User).filter(User.status != "admin")
        if search:
            q = q.filter(User.email.ilike(f"%{search}%"))
        if status:
            q = q.filter(User.status == status)
        if flagged == "true":
            q = q.filter(User.risk_flag == True)
        users = q.order_by(User.created_at.desc()).limit(200).all()
        result = []
        for u in users:
            wallet = db.query(Wallet).filter(Wallet.user_id == u.id).first()
            key_count = db.query(APIKey).filter(APIKey.user_id == u.id, APIKey.status == "active").count()
            usage_count = db.query(UsageRecord).filter(UsageRecord.user_id == u.id).count()
            ent_count = db.query(Entitlement).filter(Entitlement.user_id == u.id, Entitlement.status == "active", Entitlement.expires_at > datetime.now(timezone.utc)).count()
            result.append({"id": u.id, "email": u.email, "status": u.status, "risk_flag": bool(u.risk_flag), "created_at": u.created_at.isoformat(), "balance": float(wallet.available_balance) if wallet else 0, "reserved": float(wallet.reserved_balance) if wallet else 0, "active_keys": key_count, "total_requests": usage_count, "active_plans": ent_count})
        return result
    finally:
        db.close()

@router.get("/users/{user_id}")
async def user_detail(user_id: int, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
        usage = db.query(UsageRecord).filter(UsageRecord.user_id == user_id).order_by(UsageRecord.created_at.desc()).limit(20).all()
        ledger = db.query(WalletLedger).filter(WalletLedger.user_id == user_id).order_by(WalletLedger.created_at.desc()).limit(20).all()
        ents = db.query(Entitlement).filter(Entitlement.user_id == user_id).all()
        return {
            "user": {"id": user.id, "email": user.email, "status": user.status, "risk_flag": bool(user.risk_flag), "created_at": user.created_at.isoformat()},
            "wallet": {"available": float(wallet.available_balance), "reserved": float(wallet.reserved_balance)} if wallet else {"available": 0, "reserved": 0},
            "keys": [{"id": k.id, "prefix": k.prefix, "name": k.name, "status": k.status, "created_at": k.created_at.isoformat()} for k in keys],
            "recent_usage": [{"id": r.id, "model": r.model, "input_tokens": r.input_tokens, "output_tokens": r.output_tokens, "cost": float(r.cost), "created_at": r.created_at.isoformat()} for r in usage],
            "recent_ledger": [{"id": e.id, "type": e.entry_type, "amount": float(e.amount), "balance_after": float(e.balance_after), "created_at": e.created_at.isoformat()} for e in ledger],
            "entitlements": [{"id": e.id, "plan_id": e.plan_id, "status": e.status, "expires_at": e.expires_at.isoformat()} for e in ents],
        }
    finally:
        db.close()

@router.post("/users/adjust-balance")
async def adjust_balance(req: BalanceAdjust, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == req.user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        amount = Decimal(str(req.amount))
        if req.amount < 0:
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
            if wallet and wallet.available_balance + amount < 0:
                raise HTTPException(status_code=400, detail="Cannot make balance negative")
        result = WALLET_SERVICE.topup(db, user.id, amount, idempotency_key=f"admin-{admin.id}-{user.id}-{int(datetime.now(timezone.utc).timestamp()*1000)}")
        audit_log(db, admin.id, "adjust_balance", "user", str(user.id), f"amount={req.amount} reason={req.reason}")
        db.commit()
        return {"message": f"Balance adjusted by RM {req.amount} for user {user.id}", "new_balance": result["new_balance"], "reason": req.reason}
    except HTTPException:
        raise
    finally:
        db.close()

@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: int, req: UserSuspend, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if user.status == "admin":
            raise HTTPException(status_code=400, detail="Cannot suspend another admin")
        user.status = "suspended"
        keys = db.query(APIKey).filter(APIKey.user_id == user.id, APIKey.status == "active").all()
        for k in keys:
            k.status = "revoked"
            k.revoked_at = datetime.now(timezone.utc)
        audit_log(db, admin.id, "suspend_user", "user", str(user_id), f"reason={req.reason} revoked_keys={len(keys)}")
        db.commit()
        return {"message": f"User {user_id} suspended", "revoked_keys": len(keys)}
    finally:
        db.close()

@router.post("/users/{user_id}/activate")
async def activate_user(user_id: int, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.status = "active"
        audit_log(db, admin.id, "activate_user", "user", str(user_id), None)
        db.commit()
        return {"message": f"User {user_id} activated"}
    finally:
        db.close()

@router.post("/users/{user_id}/risk-flag")
async def toggle_risk_flag(user_id: int, req: RiskFlag, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.risk_flag = req.flagged
        audit_log(db, admin.id, "risk_flag", "user", str(user_id), f"flagged={req.flagged} reason={req.reason}")
        db.commit()
        return {"message": f"User {user_id} risk flag {'set' if req.flagged else 'cleared'}"}
    finally:
        db.close()

@router.get("/pricing")
async def get_pricing(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        provider_prices = db.query(ProviderPrice).filter(ProviderPrice.is_current == 1).all()
        customer_prices = db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).all()
        pp_map = {p.model: p for p in provider_prices}
        cp_map = {c.model: c for c in customer_prices}
        all_models = sorted(set(list(pp_map.keys()) + list(cp_map.keys())))
        return [{
            "model": m,
            "group_name": cp_map[m].group_name if m in cp_map else None,
            "input_cost": float(pp_map[m].input_cost_per_token) if m in pp_map else None,
            "output_cost": float(pp_map[m].output_cost_per_token) if m in pp_map else None,
            "cache_write_cost": float(pp_map[m].cache_write_cost_per_token) if m in pp_map else None,
            "cache_read_cost": float(pp_map[m].cache_read_cost_per_token) if m in pp_map else None,
            "cost_version": pp_map[m].version if m in pp_map else None,
            "input_sell": float(cp_map[m].input_sell_per_token) if m in cp_map else None,
            "output_sell": float(cp_map[m].output_sell_per_token) if m in cp_map else None,
            "cache_write_sell": float(cp_map[m].cache_write_sell_per_token) if m in cp_map else None,
            "cache_read_sell": float(cp_map[m].cache_read_sell_per_token) if m in cp_map else None,
            "sell_version": cp_map[m].version if m in cp_map else None,
            "margin_note": "sell - cost",
        } for m in all_models]
    finally:
        db.close()

@router.post("/pricing")
async def update_pricing(req: PriceUpdate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        if req.group_name and not db.query(ModelGroup).filter(ModelGroup.name == req.group_name).first():
            raise HTTPException(status_code=400, detail="模型分组不存在")
        old_pp = db.query(ProviderPrice).filter(ProviderPrice.model == req.model, ProviderPrice.is_current == 1).first()
        if old_pp:
            old_pp.is_current = 0
        pp = ProviderPrice(
            model=req.model,
            input_cost_per_token=Decimal(str(req.input_cost_per_token)),
            output_cost_per_token=Decimal(str(req.output_cost_per_token)),
            cache_write_cost_per_token=Decimal(str(req.cache_write_cost_per_token or 0)),
            cache_read_cost_per_token=Decimal(str(req.cache_read_cost_per_token or 0)),
            version=(old_pp.version + 1 if old_pp else 1),
            is_current=1,
            updated_by=admin.id,
        )
        db.add(pp)
        old_cp = db.query(CustomerPrice).filter(CustomerPrice.model == req.model, CustomerPrice.is_current == 1).first()
        if old_cp:
            old_cp.is_current = 0
        cp = CustomerPrice(model=req.model, input_sell_per_token=Decimal(str(req.input_sell_per_token)), output_sell_per_token=Decimal(str(req.output_sell_per_token)), version=(old_cp.version + 1 if old_cp else 1), is_current=1, updated_by=admin.id)
        cp.cache_write_sell_per_token = Decimal(str(req.cache_write_sell_per_token or 0))
        cp.cache_read_sell_per_token = Decimal(str(req.cache_read_sell_per_token or 0))
        cp.group_name = req.group_name or old_cp.group_name
        db.add(cp)
        audit_log(db, admin.id, "update_pricing", "model", req.model, f"in_cost={req.input_cost_per_token} out_cost={req.output_cost_per_token} in_sell={req.input_sell_per_token} out_sell={req.output_sell_per_token}")
        db.commit()
        return {"message": f"Pricing updated for {req.model}", "cost_version": pp.version, "sell_version": cp.version}
    finally:
        db.close()

@router.get("/pricing-groups")
async def get_pricing_groups(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        groups = db.query(ModelGroup).order_by(ModelGroup.sort_order, ModelGroup.id).all()
        models = db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).all()
        keys = db.query(APIKey).all()
        counts = {group.name: 0 for group in groups}
        key_counts = {group.name: 0 for group in groups}
        for model in models:
            if model.group_name in counts:
                counts[model.group_name] += 1
        for key in keys:
            if key.group_name in key_counts:
                key_counts[key.group_name] += 1
        return [{"id": group.id, "name": group.name, "sort_order": group.sort_order, "model_count": counts[group.name], "key_count": key_counts[group.name], "created_at": group.created_at.isoformat()} for group in groups]
    finally:
        db.close()

@router.get("/model-multipliers")
async def list_model_multipliers(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        models = db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).order_by(CustomerPrice.model).all()
        rows = db.query(ModelMultiplier).all()
        rows_map = {row.model: parse_hourly_multipliers(row.hourly_multipliers) for row in rows}
        return [{"model": model.model, "hourly_multipliers": rows_map.get(model.model, parse_hourly_multipliers(None))} for model in models]
    finally:
        db.close()

@router.get("/model-multiplier-day")
async def get_model_multiplier_day(model: str, business_date: str, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        row = db.query(DailyMultiplier).filter(DailyMultiplier.model == model, DailyMultiplier.business_date == business_date).first()
        return {"model": model, "business_date": business_date, "hourly_multipliers": parse_hourly_multipliers(row.hourly_multipliers if row else None)}
    finally:
        db.close()

@router.post("/model-multiplier-day")
async def update_model_multiplier_day(req: DailyMultipliersUpdate, admin: User = Depends(require_admin)):
    if len(req.hourly_multipliers) != 24:
        raise HTTPException(status_code=400, detail="一天的曲线必须包含 24 个小时倍数")
    if any(value <= 0 or value > 10 for value in req.hourly_multipliers):
        raise HTTPException(status_code=400, detail="小时的倍数必须在 0.01 到 10 之间")
    db = SessionLocal()
    try:
        row = db.query(DailyMultiplier).filter(DailyMultiplier.model == req.model, DailyMultiplier.business_date == req.business_date).first()
        if row is None:
            row = DailyMultiplier(model=req.model, business_date=req.business_date, hourly_multipliers="")
            db.add(row)
        row.hourly_multipliers = json.dumps([round(float(value), 4) for value in req.hourly_multipliers])
        audit_log(db, admin.id, "update_daily_multiplier", "model", req.model, f"{req.business_date} curve updated")
        db.commit()
        return {"message": f"{req.model} {req.business_date} 峰谷倍数已更新", "hourly_multipliers": parse_hourly_multipliers(row.hourly_multipliers)}
    finally:
        db.close()

@router.post("/model-multipliers")
async def update_model_multipliers(req: HourlyMultipliersUpdate, admin: User = Depends(require_admin)):
    if len(req.hourly_multipliers) != 24:
        raise HTTPException(status_code=400, detail="峰值曲线必须包含 24 个小时倍数")
    if any(value <= 0 or value > 10 for value in req.hourly_multipliers):
        raise HTTPException(status_code=400, detail="小时的倍数必须在 0.01 到 10 之间")
    db = SessionLocal()
    try:
        row = db.query(ModelMultiplier).filter(ModelMultiplier.model == req.model).first()
        if row is None:
            row = ModelMultiplier(model=req.model, hourly_multipliers="")
            db.add(row)
        row.hourly_multipliers = json.dumps([round(float(value), 4) for value in req.hourly_multipliers])
        row.version = (row.version or 1) + 1
        audit_log(db, admin.id, "update_model_multiplier", "model", req.model, "24h curve updated")
        db.commit()
        return {"message": "峰谷倍数已更新", "model": req.model, "hourly_multipliers": parse_hourly_multipliers(row.hourly_multipliers)}
    finally:
        db.close()

@router.post("/pricing-groups")
async def create_pricing_group(req: PricingGroupCreate, admin: User = Depends(require_admin)):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名称不能为空")
    db = SessionLocal()
    try:
        existing = db.query(ModelGroup).filter(ModelGroup.name == name).first()
        if existing:
            raise HTTPException(status_code=409, detail="分组名称已存在")
        last = db.query(ModelGroup).order_by(ModelGroup.sort_order.desc(), ModelGroup.id.desc()).first()
        group = ModelGroup(name=name, sort_order=(last.sort_order + 1 if last and last.sort_order else 1))
        db.add(group)
        audit_log(db, admin.id, "create_pricing_group", "model_group", name, name)
        db.commit()
        db.refresh(group)
        return {"message": "分组已创建", "id": group.id, "name": group.name, "model_count": 0}
    finally:
        db.close()

@router.delete("/pricing-groups/{group_id}")
async def delete_pricing_group(group_id: int, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        group = db.query(ModelGroup).filter(ModelGroup.id == group_id).first()
        if group is None:
            raise HTTPException(status_code=404, detail="分组不存在")
        model_count = db.query(CustomerPrice).filter(CustomerPrice.group_name == group.name, CustomerPrice.is_current == 1).count()
        key_count = db.query(APIKey).filter(APIKey.group_name == group.name).count()
        if model_count or key_count:
            raise HTTPException(status_code=400, detail="请先删除或迁移组内模型，并解绑使用中的 API Key")
        db.delete(group)
        audit_log(db, admin.id, "delete_pricing_group", "model_group", group.name, group.name)
        db.commit()
        return {"message": "分组已删除", "id": group_id}
    finally:
        db.close()

@router.post("/pricing-groups/{group_id}/rename")
async def rename_pricing_group(group_id: int, req: PricingGroupCreate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        group = db.query(ModelGroup).filter(ModelGroup.id == group_id).first()
        if group is None:
            raise HTTPException(status_code=404, detail="分组不存在")
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分组名称不能为空")
        duplicate = db.query(ModelGroup).filter(ModelGroup.name == name, ModelGroup.id != group_id).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="分组名称已存在")
        old_name = group.name
        db.query(CustomerPrice).filter(CustomerPrice.group_name == old_name).update({"group_name": name}, synchronize_session=False)
        db.query(APIKey).filter(APIKey.group_name == old_name).update({"group_name": name}, synchronize_session=False)
        group.name = name
        audit_log(db, admin.id, "rename_pricing_group", "model_group", name, f"old_name={old_name}")
        db.commit()
        return {"message": "分组名称已更新", "id": group.id, "name": group.name}
    finally:
        db.close()

@router.delete("/pricing/{model}")
async def delete_pricing(model: str, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        customer_price = db.query(CustomerPrice).filter(CustomerPrice.model == model, CustomerPrice.is_current == 1).first()
        provider_price = db.query(ProviderPrice).filter(ProviderPrice.model == model, ProviderPrice.is_current == 1).first()
        route = db.query(SupplierRoute).filter(SupplierRoute.model_name == model).first()
        if not customer_price and not provider_price and not route:
            raise HTTPException(status_code=404, detail="Model not found")
        db.query(CustomerPrice).filter(CustomerPrice.model == model).delete()
        db.query(ProviderPrice).filter(ProviderPrice.model == model).delete()
        db.query(SupplierRoute).filter(SupplierRoute.model_name == model).delete()
        audit_log(db, admin.id, "delete_pricing", "model", model, "pricing and route deleted")
        db.commit()
        return {"message": f"Model {model} 已删除"}
    finally:
        db.close()

@router.get("/providers")
async def get_providers(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        providers = db.query(Provider).order_by(Provider.priority).all()
        return [{"id": p.id, "name": p.name, "api_base_url": p.api_base_url, "status": p.status, "priority": p.priority, "key_status": p.key_status, "last_error": p.last_error, "created_at": p.created_at.isoformat()} for p in providers]
    finally:
        db.close()

@router.post("/providers")
async def update_provider(req: ProviderUpdate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        existing = db.query(Provider).filter(Provider.name == req.name).first()
        if existing:
            existing.api_base_url = req.api_base_url or existing.api_base_url
            existing.status = req.status
            existing.priority = req.priority
            audit_log(db, admin.id, "update_provider", "provider", req.name, f"status={req.status} priority={req.priority}")
            db.commit()
            return {"message": f"Provider {req.name} updated"}
        p = Provider(name=req.name, api_base_url=req.api_base_url, status=req.status, priority=req.priority)
        db.add(p)
        audit_log(db, admin.id, "create_provider", "provider", req.name, None)
        db.commit()
        return {"message": f"Provider {req.name} created"}
    finally:
        db.close()

@router.get("/suppliers")
async def get_suppliers(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        suppliers = db.query(Supplier).order_by(Supplier.priority, Supplier.id).all()
        return [{
            "id": s.id, "name": s.name, "status": s.status, "priority": s.priority,
            "contact_email": s.contact_email, "notes": s.notes, "created_at": s.created_at.isoformat(),
            "routes": db.query(SupplierRoute).filter(SupplierRoute.supplier_id == s.id).count(),
        } for s in suppliers]
    finally:
        db.close()

@router.post("/suppliers")
async def create_supplier(req: SupplierCreate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        if db.query(Supplier).filter(Supplier.name == req.name).first():
            raise HTTPException(status_code=409, detail="Supplier name already exists")
        supplier = Supplier(name=req.name, status=req.status, priority=req.priority, contact_email=req.contact_email, notes=req.notes)
        db.add(supplier)
        audit_log(db, admin.id, "create_supplier", "supplier", req.name, None)
        db.commit()
        db.refresh(supplier)
        return {"message": f"Supplier {req.name} created", "id": supplier.id}
    finally:
        db.close()

@router.get("/supplier-routes")
async def get_supplier_routes(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        routes = db.query(SupplierRoute).order_by(SupplierRoute.model_name).all()
        supplier_map = {s.id: s.name for s in db.query(Supplier).all()}
        return [{
            "id": r.id, "supplier_id": r.supplier_id, "supplier_name": supplier_map.get(r.supplier_id, "Unknown"),
            "model_name": r.model_name, "upstream_model": r.upstream_model, "endpoint_url": r.endpoint_url,
            "protocol": r.protocol, "api_key_last4": r.api_key_last4, "status": r.status,
            "priority": r.priority, "key_status": r.key_status, "last_error": r.last_error,
            "updated_at": r.updated_at.isoformat(),
        } for r in routes]
    finally:
        db.close()

@router.post("/supplier-routes")
async def create_supplier_route(req: SupplierRouteCreate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        if not db.query(CustomerPrice).filter(CustomerPrice.model == req.model_name, CustomerPrice.is_current == 1).first():
            raise HTTPException(status_code=400, detail="Create customer pricing for this model first")
        supplier = db.query(Supplier).order_by(Supplier.priority, Supplier.id).first()
        if supplier is None:
            supplier = Supplier(name="Default Supplier", status="active", priority=1, notes="Auto-created supplier container")
            db.add(supplier)
            db.flush()
        if db.query(SupplierRoute).filter(SupplierRoute.model_name == req.model_name).first():
            raise HTTPException(status_code=409, detail="A route already exists for this model")
        if not req.endpoint_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Endpoint URL must be http or https")
        protocol = "anthropic" if "/v1/messages" in req.endpoint_url or "/anthropic" in req.endpoint_url else "openai"
        route = SupplierRoute(
            supplier_id=supplier.id, model_name=req.model_name, upstream_model=req.upstream_model,
            endpoint_url=req.endpoint_url, protocol=protocol, api_key_encrypted=encrypt_secret(req.api_key),
            api_key_last4=secret_suffix(req.api_key), status="active", priority=req.priority,
        )
        db.add(route)
        audit_log(db, admin.id, "create_supplier_route", "model", req.model_name, f"supplier={supplier.name} protocol={protocol} endpoint={req.endpoint_url}")
        db.commit()
        return {"message": f"Supplier route created for {req.model_name}", "id": route.id}
    finally:
        db.close()

@router.post("/supplier-routes/{route_id}")
async def update_supplier_route(route_id: int, req: SupplierRouteUpdate, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        route = db.query(SupplierRoute).filter(SupplierRoute.id == route_id).first()
        if route is None:
            raise HTTPException(status_code=404, detail="Supplier route not found")
        route.upstream_model = req.upstream_model
        route.endpoint_url = req.endpoint_url
        route.protocol = "anthropic" if "/v1/messages" in req.endpoint_url or "/anthropic" in req.endpoint_url else "openai"
        if req.api_key:
            route.api_key_encrypted = encrypt_secret(req.api_key)
            route.api_key_last4 = secret_suffix(req.api_key)
            route.key_status = "unknown"
            route.last_error = None
        audit_log(db, admin.id, "update_supplier_route", "model", route.model_name, f"protocol={route.protocol} endpoint={route.endpoint_url}")
        db.commit()
        return {"message": f"Supplier route updated for {route.model_name}"}
    finally:
        db.close()

@router.delete("/supplier-routes/{route_id}")
async def delete_supplier_route(route_id: int, admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        route = db.query(SupplierRoute).filter(SupplierRoute.id == route_id).first()
        if route is None:
            raise HTTPException(status_code=404, detail="Supplier route not found")
        model_name = route.model_name
        db.delete(route)
        audit_log(db, admin.id, "delete_supplier_route", "model", model_name, None)
        db.commit()
        return {"message": f"Supplier route deleted for {model_name}"}
    finally:
        db.close()

@router.post("/accounting/reset")
async def reset_accounting(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        db.query(UsageRecord).delete(synchronize_session=False)
        db.query(WalletLedger).delete(synchronize_session=False)
        wallets = db.query(Wallet).with_for_update().all()
        for wallet in wallets:
            wallet.reserved_balance = 0
            wallet.available_balance = Decimal("100.00") if wallet.user and wallet.user.email == "ngdarren0852@gmail.com" else Decimal("0.00")
            wallet.version = (wallet.version or 0) + 1
        audit_log(db, admin.id, "reset_accounting", "system", None, "Clear usage records, ledger and reset wallets.")
        db.commit()
        return {"message": "测试账本已重置，管理员钱包已设为 RM 100.00"}
    finally:
        db.close()

@router.get("/analytics/series")
async def get_analytics_series(range: str = "today", admin: User = Depends(require_admin)):
    from datetime import timedelta, timezone as dt_timezone
    from decimal import Decimal

    db = SessionLocal()
    try:
        tz = dt_timezone(timedelta(hours=8))
        now = datetime.now(tz)
        if range == "month":
            start = datetime(now.year, now.month, 1, tzinfo=tz)
            end = None
            bucket_count = 31
            bucket_seconds = 86400
            labels = [str(day) for day in range(1, 32)]
        elif range == "year":
            start = datetime(now.year, 1, 1, tzinfo=tz)
            end = None
            bucket_count = 12
            bucket_seconds = 31 * 86400
            labels = [f"{month:02d}月" for month in range(1, 13)]
        else:
            start = datetime(now.year, now.month, now.day, tzinfo=tz)
            end = None
            bucket_count = 24
            bucket_seconds = 3600
            labels = [f"{hour:02d}:00" for hour in range(24)]
        period_start = start
        period_end = period_start + timedelta(seconds=bucket_seconds * bucket_count)
        records = db.query(UsageRecord).filter(UsageRecord.created_at >= period_start, UsageRecord.created_at < period_end).all()
        input_series = [0] * bucket_count
        output_series = [0] * bucket_count
        cache_write_series = [0] * bucket_count
        cache_read_series = [0] * bucket_count
        revenue_series = [0.0] * bucket_count
        supplier_cost_series = [0.0] * bucket_count
        price_map = {row.model: row for row in db.query(ProviderPrice).filter(ProviderPrice.is_current == 1).all()}
        model_to_group = {row.model: row.group_name for row in db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).all()}
        group_names = []
        group_series = {}
        for record in records:
            if record.created_at is None:
                continue
            item_time = record.created_at
            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=dt_timezone.utc)
            local_time = item_time.astimezone(tz)
            offset = int((local_time - period_start).total_seconds() // bucket_seconds)
            if offset < 0 or offset >= bucket_count:
                continue
            input_tokens = record.input_tokens or 0
            output_tokens = record.output_tokens or 0
            cache_write_tokens = record.cache_write_tokens or 0
            cache_read_tokens = record.cache_read_tokens or 0
            input_series[offset] += input_tokens
            output_series[offset] += output_tokens
            cache_write_series[offset] += cache_write_tokens
            cache_read_series[offset] += cache_read_tokens
            revenue_series[offset] += float(record.cost or 0)
            price = price_map.get(record.model)
            if price:
                cost = (
                    Decimal(str(max(input_tokens - cache_read_tokens - cache_write_tokens, 0))) * price.input_cost_per_token
                    + Decimal(str(output_tokens)) * price.output_cost_per_token
                    + Decimal(str(cache_write_tokens)) * price.cache_write_cost_per_token
                    + Decimal(str(cache_read_tokens)) * price.cache_read_cost_per_token
                ) / Decimal("1000000")
                supplier_cost_series[offset] += float(cost)
            group_name = model_to_group.get(record.model) or "未分组"
            if group_name not in group_series:
                group_names.append(group_name)
                group_series[group_name] = [0] * bucket_count
            group_series[group_name][offset] += input_tokens + output_tokens + cache_write_tokens + cache_read_tokens
        ledger_rows = db.query(WalletLedger).join(User, User.id == WalletLedger.user_id).filter(WalletLedger.created_at >= period_start, WalletLedger.created_at < period_end, User.status != "admin").order_by(WalletLedger.created_at).all()
        current_customer_wallet, _admin_wallet, _customer_usage = _wallet_summary(db)
        period_ledger_amount = sum(float(row.amount or 0) for row in ledger_rows)
        opening_balance = float(current_customer_wallet) - period_ledger_amount
        wallet_series = [0.0] * bucket_count
        carry = float(opening_balance)
        for ledger in ledger_rows:
            if ledger.created_at is None:
                continue
            item_time = ledger.created_at
            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=dt_timezone.utc)
            local_time = item_time.astimezone(tz)
            offset = int((local_time - period_start).total_seconds() // bucket_seconds)
            if offset < 0 or offset >= bucket_count:
                continue
            # For simplicity, each bucket shows cumulative balance at that point in the period.
            wallet_series[offset] = carry + float(ledger.amount or 0)
            carry += float(ledger.amount or 0)
        profit_series = [float(revenue_series[i]) - float(supplier_cost_series[i]) for i in range(bucket_count)]
        return {
            "range": range,
            "buckets": labels,
            "usage": {
                "input": input_series,
                "output": output_series,
                "cache_write": cache_write_series,
                "cache_read": cache_read_series,
            },
            "revenue": revenue_series,
            "supplier_cost": supplier_cost_series,
            "profit": profit_series,
            "wallet_balance": wallet_series,
            "groups": [
                {"name": name, "series": group_series[name]}
                for name in group_names
            ],
        }
    finally:
        db.close()

@router.get("/analytics/overview")
async def get_analytics_overview(admin: User = Depends(require_admin)):
    from datetime import timedelta, timezone as dt_timezone
    from decimal import Decimal
    from sqlalchemy import func

    db = SessionLocal()
    try:
        tz = dt_timezone(timedelta(hours=8))
        now = datetime.now(tz)
        if now.month == 12:
            year_end = datetime(now.year + 1, 1, 1, tzinfo=tz)
        else:
            year_end = datetime(now.year + 1, 1, 1, tzinfo=tz)
        year_start = datetime(now.year, 1, 1, tzinfo=tz)
        period_start = year_start
        period_end = year_end
        records = db.query(UsageRecord).filter(UsageRecord.created_at >= period_start, UsageRecord.created_at < period_end).all()
        price_map = {
            row.model: row
            for row in db.query(ProviderPrice).filter(ProviderPrice.is_current == 1).all()
        }
        total_input = sum((item.input_tokens or 0) for item in records)
        total_output = sum((item.output_tokens or 0) for item in records)
        total_cache_write = sum((item.cache_write_tokens or 0) for item in records)
        total_cache_read = sum((item.cache_read_tokens or 0) for item in records)
        revenue = sum((item.cost or 0) for item in records)
        supplier_cost_cny = Decimal("0")
        group_usage = {}
        for item in records:
            price = price_map.get(item.model)
            if price:
                supplier_cost_cny += (
                    Decimal(str(max((item.input_tokens or 0) - (item.cache_read_tokens or 0) - (item.cache_write_tokens or 0), 0))) * price.input_cost_per_token
                    + Decimal(str(item.output_tokens or 0)) * price.output_cost_per_token
                    + Decimal(str(item.cache_write_tokens or 0)) * price.cache_write_cost_per_token
                    + Decimal(str(item.cache_read_tokens or 0)) * price.cache_read_cost_per_token
                ) / Decimal("1000000")
        model_to_group = {
            row.model: row.group_name
            for row in db.query(CustomerPrice).filter(CustomerPrice.is_current == 1).all()
        }
        for item in records:
            group_name = model_to_group.get(item.model) or "未分组"
            group_usage[group_name] = group_usage.get(group_name, 0) + (item.input_tokens or 0) + (item.output_tokens or 0) + (item.cache_read_tokens or 0) + (item.cache_write_tokens or 0)
        customer_wallet, admin_wallet, customer_usage = _wallet_summary(db)
        return {
            "total_input": int(total_input),
            "total_output": int(total_output),
            "total_cache_write": int(total_cache_write),
            "total_cache_read": int(total_cache_read),
            "revenue": float(revenue),
            "supplier_cost_cny": float(supplier_cost_cny),
            "group_usage": [
                {"name": key, "tokens": value, "share": float(value) / float(total_input + total_output + total_cache_read + total_cache_write) * 100 if (total_input + total_output + total_cache_read + total_cache_write) else 0}
                for key, value in group_usage.items()
            ],
            "customer_wallet_balance": float(customer_wallet),
            "customer_usage": float(customer_usage),
        }
    finally:
        db.close()

@router.get("/finance")
async def get_finance(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        from sqlalchemy import func
        topups = db.query(func.coalesce(func.sum(WalletLedger.amount), 0)).filter(WalletLedger.entry_type == "topup").scalar()
        usage_total = db.query(func.coalesce(func.sum(WalletLedger.amount), 0)).filter(WalletLedger.entry_type == "usage").scalar()
        plan_purchases = db.query(func.coalesce(func.sum(WalletLedger.amount), 0)).filter(WalletLedger.entry_type == "plan_purchase").scalar()
        admin_adjusts = db.query(func.coalesce(func.sum(WalletLedger.amount), 0)).filter(WalletLedger.entry_type == "topup", WalletLedger.reference_type == "manual").scalar()
        wallet_rows = db.query(Wallet).with_entities(Wallet.available_balance).all()
        total_wallet = sum(w[0] for w in wallet_rows) if wallet_rows else 0
        reserved_rows = db.query(Wallet).with_entities(Wallet.reserved_balance).all()
        total_reserved = sum(w[0] for w in reserved_rows) if reserved_rows else 0
        customer_wallet, admin_wallet, _unused_usage = _wallet_summary(db)
        return {
            "total_topups": float(topups or 0),
            "total_usage_billed": float(usage_total or 0),
            "total_plan_purchases": float(plan_purchases or 0),
            "total_wallet_balance": float(total_wallet),
            "total_reserved": float(total_reserved),
            "total_customer_wallet_balance": float(customer_wallet),
            "admin_wallet_balance": float(admin_wallet),
            "total_supplier_cost_cny": float(_supplier_cost_cny(db)),
        }
    finally:
        db.close()

@router.get("/ledger")
async def get_all_ledger(admin: User = Depends(require_admin), entry_type: str = None):
    db = SessionLocal()
    try:
        q = db.query(WalletLedger).order_by(WalletLedger.created_at.desc())
        if entry_type:
            q = q.filter(WalletLedger.entry_type == entry_type)
        entries = q.limit(200).all()
        return [{"id": e.id, "user_id": e.user_id, "type": e.entry_type, "amount": float(e.amount), "balance_after": float(e.balance_after), "reference": e.reference_type, "idempotency_key": e.idempotency_key, "created_at": e.created_at.isoformat()} for e in entries]
    finally:
        db.close()

@router.get("/audit")
async def get_audit(admin: User = Depends(require_admin)):
    db = SessionLocal()
    try:
        entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
        admin_map = {}
        for e in entries:
            if e.admin_id not in admin_map:
                a = db.query(User).filter(User.id == e.admin_id).first()
                admin_map[e.admin_id] = a.email if a else str(e.admin_id)
        return [{"id": e.id, "admin": admin_map.get(e.admin_id, str(e.admin_id)), "action": e.action, "target_type": e.target_type, "target_id": e.target_id, "detail": e.detail, "created_at": e.created_at.isoformat()} for e in entries]
    finally:
        db.close()
