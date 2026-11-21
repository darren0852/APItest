"""Sprint 4 tests: Plans/Subscription."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def setup_user(password="planpass123"):
    email = f"plan_{int(time.time()*1000)}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    token = r.json()["token"]
    return email, token

def get_token(email, password="planpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["token"]

def test_list_plans():
    resp = client.get("/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) >= 3
    names = [p["name"] for p in plans]
    assert "Starter" in names
    assert "Pro" in names
    assert "Unlimited" in names

def test_purchase_plan_insufficient():
    email, token = setup_user()
    resp = client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 402

def test_purchase_plan_success():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Starter" in data["message"]
    assert data["balance"] == 40.0

def test_entitlement_after_purchase():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/me/entitlement", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ents = resp.json()
    assert len(ents) >= 1
    assert ents[0]["plan_name"] == "Starter"

def test_plan_request_daily_limit():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    for i in range(55):
        resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}, headers=headers)
        if resp.status_code == 402 and "Daily request limit" in resp.json().get("detail", ""):
            break
    assert resp.status_code == 402
    assert "Daily request limit" in resp.json().get("detail", "")

def test_plan_daily_reset():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    from plans import PlanService, Entitlement
    from database import SessionLocal
    from datetime import date, timedelta
    db = SessionLocal()
    ent = db.query(Entitlement).filter(Entitlement.plan_id == 1).order_by(Entitlement.id.desc()).first()
    ent.daily_requests_used = 50
    ent.daily_reset_date = date.today() - timedelta(days=1)
    db.commit()
    status, result = PlanService.check_entitlement(db, ent.user_id, "mock-model")
    db.close()
    assert status == "plan"
    assert result.daily_requests_used == 0

def test_plan_ledger_entry():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/me/ledger", headers={"Authorization": f"Bearer {token}"})
    entries = resp.json()
    types = [e["type"] for e in entries]
    assert "plan_purchase" in types

def test_purchase_invalid_plan():
    email, token = setup_user()
    resp = client.post("/plans/purchase", json={"plan_id": 999}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

def test_usage_records_after_plan_call():
    email, token = setup_user()
    client.post("/billing/topups", json={"amount": 50.0}, headers={"Authorization": f"Bearer {token}"})
    client.post("/plans/purchase", json={"plan_id": 1}, headers={"Authorization": f"Bearer {token}"})
    key_resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    raw_key = key_resp.json()["key"]
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}, headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 200
    usage_resp = client.get("/me/usage", headers={"Authorization": f"Bearer {token}"})
    records = usage_resp.json()
    assert len(records) >= 1