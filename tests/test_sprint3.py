"""Sprint 3 tests: Wallet, Ledger, Billing."""
import sys, os, time, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def setup_user(email=None, password="walletpass123"):
    email = email or f"wallet_{int(time.time()*1000)}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    token = r.json()["token"]
    return email, token

def test_topup_positive():
    email, token = setup_user()
    resp = client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 50.0

def test_topup_negative_rejected():
    email, token = setup_user()
    resp = client.post("/billing/topups", json={"amount": -10}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

def test_topup_below_minimum():
    email, token = setup_user()
    resp = client.post("/billing/topups", json={"amount": 0.50}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

def test_topup_multiple():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 10.0}, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/billing/topups", json={"amount": 20.0}, headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["balance"] == 30.0

def test_balance():
    email, token = setup_user()
    resp = client.get("/me/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["available"] == 0

def test_balance_after_topup():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 100.0}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/me/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["available"] == 100.0

def test_ledger_after_topup():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 10.0}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/me/ledger", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1
    assert entries[0]["type"] == "topup"

def test_chat_insufficient_balance():
    email, token = setup_user()
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}, headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 402

def test_chat_with_balance():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}, headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 200
    assert "request_id" in resp.json()

def test_ledger_after_usage():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}, headers={"Authorization": f"Bearer {raw_key}"})
    resp = client.get("/me/ledger", headers={"Authorization": f"Bearer {token}"})
    entries = resp.json()
    types = [e["type"] for e in entries]
    assert "topup" in types
    assert "usage" in types

def test_unknown_model_rejected():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    resp = client.post("/v1/chat/completions", json={"model": "unknown-model", "messages": [{"role": "user", "content": "hello"}]}, headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 400