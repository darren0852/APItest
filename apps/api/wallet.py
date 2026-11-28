"""Wallet service with ledger-based accounting."""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from database import SessionLocal, Wallet, WalletLedger, UsageRecord, APIKey, User
import uuid
import json

class WalletService:
    @staticmethod
    def ensure_wallet(db, user_id: int) -> Wallet:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if wallet is None:
            wallet = Wallet(user_id=user_id, available_balance=Decimal("0"), reserved_balance=Decimal("0"))
            db.add(wallet)
            db.flush()
        return wallet

    @staticmethod
    def topup(db, user_id: int, amount: Decimal, idempotency_key: str = None) -> dict:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
        if wallet is None:
            wallet = WalletService.ensure_wallet(db, user_id)
        new_balance = wallet.available_balance + amount
        wallet.available_balance = new_balance
        wallet.version += 1
        ledger = WalletLedger(
            user_id=user_id,
            entry_type="topup",
            amount=amount,
            currency=wallet.currency,
            balance_after=new_balance,
            reference_type="manual",
            reference_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
        db.add(ledger)
        return {"new_balance": float(new_balance), "ledger_id": ledger.id}

    @staticmethod
    def check_balance(db, user_id: int, estimated_cost: Decimal) -> bool:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if wallet is None:
            return False
        return wallet.available_balance >= estimated_cost

    @staticmethod
    def reserve(db, user_id: int, amount: Decimal) -> bool:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
        if wallet is None or wallet.available_balance < amount:
            return False
        wallet.available_balance -= amount
        wallet.reserved_balance += amount
        wallet.version += 1
        db.flush()
        return True

    @staticmethod
    def settle(db, user_id: int, request_id: str, reserved: Decimal, actual: Decimal) -> dict:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
        refund = reserved - actual
        if refund > 0:
            wallet.reserved_balance -= reserved
            wallet.available_balance += refund
        elif refund < 0:
            wallet.reserved_balance -= reserved
            wallet.available_balance -= abs(refund)
        else:
            wallet.reserved_balance -= reserved
        wallet.version += 1
        ledger = WalletLedger(
            user_id=user_id,
            entry_type="usage",
            amount=-actual,
            currency=wallet.currency,
            balance_after=wallet.available_balance,
            reference_type="api_request",
            reference_id=request_id,
            idempotency_key=f"usage-{request_id}",
        )
        db.add(ledger)
        return {"final_balance": float(wallet.available_balance), "charged": float(actual), "refunded": float(max(refund, Decimal("0")))}

    @staticmethod
    def get_balance(db, user_id: int) -> dict:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if wallet is None:
            return {"available": 0, "reserved": 0, "currency": "MYR"}
        return {"available": float(wallet.available_balance), "reserved": float(wallet.reserved_balance), "currency": wallet.currency}

    @staticmethod
    def record_usage(db, user_id: int, api_key_id: int, model: str, input_tokens: int, output_tokens: int, cost: Decimal, cache_read_tokens: int = 0, cache_write_tokens: int = 0):
        record = UsageRecord(user_id=user_id, api_key_id=api_key_id, model=model, input_tokens=input_tokens, output_tokens=output_tokens, cost=cost)
        if cache_read_tokens:
            record.cache_read_tokens = cache_read_tokens
        if cache_write_tokens:
            record.cache_write_tokens = cache_write_tokens
        db.add(record)
        return record

WALLET_SERVICE = WalletService()

# Model pricing (sen = 1/100 MYR)
MODEL_PRICES = {
    "mock-model": {
        "input": Decimal("0.000001"),
        "output": Decimal("0.000002"),
        "cache_write": Decimal("0"),
        "cache_read": Decimal("0"),
        "group": "DeepSeek",
    },
}


def get_model_price(db, model: str) -> dict:
    from pricing import CustomerPrice, ensure_daily_multiplier, parse_hourly_multipliers
    current = db.query(CustomerPrice).filter(CustomerPrice.model == model, CustomerPrice.is_current == 1).first()
    if current:
        business_date = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        hourly_multipliers = ensure_daily_multiplier(db, model, business_date)
        hour = datetime.now(timezone(timedelta(hours=8))).hour
        current_multiplier = hourly_multipliers[hour]
        return {
            "input": Decimal(current.input_sell_per_token) * Decimal(str(current_multiplier)),
            "output": Decimal(current.output_sell_per_token) * Decimal(str(current_multiplier)),
            "cache_write": Decimal(current.cache_write_sell_per_token) * Decimal(str(current_multiplier)),
            "cache_read": Decimal(current.cache_read_sell_per_token) * Decimal(str(current_multiplier)),
            "group": current.group_name,
            "hourly_multipliers": hourly_multipliers,
            "current_multiplier": current_multiplier,
        }
    return MODEL_PRICES.get(model)
