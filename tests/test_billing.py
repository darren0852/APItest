import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from decimal import Decimal

from main import MODEL_PRICE_SEED
from supplier import normalize_anthropic_response
from wallet import WalletService


def test_seed_prices_are_rm_customer_prices():
    assert MODEL_PRICE_SEED[0] == ("glm-5.3", "Zhipu GLM", 3.000000, 10.500000, 0.000000, 0.750000)
    assert MODEL_PRICE_SEED[3] == ("kimi-k3.1-pro-highspeed", "Kimi", 11.700000, 61.200000, 11.700000, 0.585000)


def test_anthropic_cache_usage_is_normalized():
    result = normalize_anthropic_response(
        "test",
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 30,
            },
        },
    )
    usage = result["usage"]
    assert usage["prompt_tokens"] == 210
    assert usage["prompt_tokens_details"]["cached_tokens"] == 80
    assert usage["cache_creation_input_tokens"] == 30


def test_wallet_settlement_keeps_ledger_consistent():
    from database import SessionLocal, User
    from decimal import Decimal

    db = SessionLocal()
    try:
        email = f"wallet-settle-{os.getpid()}@test.test"
        user = User(email=email, password_hash="test")
        db.add(user)
        db.flush()
        wallet = WalletService.ensure_wallet(db, user.id)
        WalletService.topup(db, user.id, Decimal("100"), f"settle-top-{os.getpid()}")
        db.commit()
        WalletService.reserve(db, user.id, Decimal("10"))
        result = WalletService.settle(db, user.id, f"settle-{os.getpid()}", Decimal("10"), Decimal("6.25"))
        db.commit()
        db.refresh(wallet)
        assert result["charged"] == 6.25
        assert float(wallet.available_balance) == 93.75
        assert float(wallet.reserved_balance) == 0
        record = WalletService.record_usage(db, user.id, None, "mock-model", 100, 20, Decimal("1.50"), cache_read_tokens=30, cache_write_tokens=40)
        db.flush()
        assert record.cache_read_tokens == 30
        assert record.cache_write_tokens == 40
    finally:
        db.rollback()
        db.close()
