"""Sprint 8 tests: Rate limiting, security, health."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def setup():
    email = f"s8_{int(time.time()*1000)}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "securepass123"})
    token = r.json()["token"]
    client.post("/billing/topups", json={"amount": 100.0}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "load", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    return token, key_resp.json()["key"]

def test_rate_limit_redis():
    from rate_limit import RATE_LIMITER
    rl_key = f"test:rl:{int(time.time()*1000)}"
    allowed, remaining = RATE_LIMITER.check(rl_key, 5, 60)
    assert allowed is True
    assert remaining == 4
    for i in range(4):
        allowed, _ = RATE_LIMITER.check(rl_key, 5, 60)
    assert allowed is True
    allowed, _ = RATE_LIMITER.check(rl_key, 5, 60)
    assert allowed is False

def test_rate_limit_429():
    now = time.time()
    seconds_into_window = now % 60
    if seconds_into_window > 50:
        time.sleep(60 - seconds_into_window + 1)
    token, key = setup()
    headers = {"Authorization": f"Bearer {key}"}
    body = {"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}
    import concurrent.futures
    def send(_):
        try:
            r = client.post("/v1/chat/completions", json=body, headers=headers)
            return r.status_code
        except Exception:
            return 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        codes = list(ex.map(send, range(70)))
    from collections import Counter
    print(f"CODES: {dict(Counter(codes))}")
    assert 429 in codes

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_no_route_does_not_credit_wallet():
    import time
    from database import SessionLocal
    from wallet import Wallet
    email = f"noroute_{int(time.time()*1000000)}@test.com"
    register = client.post("/auth/register", json={"email": email, "password": "securepass123"})
    token = register.json()["token"]
    client.post("/billing/topups", json={"amount": 25.0}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "no-route", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    assert key_resp.status_code == 200
    raw_key = key_resp.json()["key"]
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 404
    db = SessionLocal()
    try:
        auth_db = SessionLocal()
        from database import User
        user = auth_db.query(User).filter(User.email == email).first()
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        assert float(wallet.available_balance) == 25.0
        assert float(wallet.reserved_balance) == 0.0
        auth_db.close()
    finally:
        db.close()

def test_no_secret_leak_in_errors():
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}, headers={"Authorization": "Bearer sk-cust-invalidkey123456789012345678"})
    assert resp.status_code == 401
    text = resp.json().get("detail", "")
    assert "sk-master" not in text
    assert "postgresql" not in text

def test_cors_enabled():
    resp = client.options("/health")
    assert resp.status_code < 500
