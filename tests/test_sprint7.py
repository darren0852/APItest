"""Sprint 7 tests: Admin panel."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def setup_admin(password="adminpass123"):
    email = f"admin_{int(time.time()*1000)}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    token = r.json()["token"]
    user_id = r.json()["user_id"]
    from database import SessionLocal, User
    db = SessionLocal()
    u = db.query(User).filter(User.id == user_id).first()
    u.status = "admin"
    db.commit()
    db.close()
    return email, token, user_id

def setup_regular(password="userpass123"):
    email = f"user_{int(time.time()*1000)}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    token = r.json()["token"]
    user_id = r.json()["user_id"]
    return email, token, user_id

def test_admin_users_requires_admin():
    email, token, uid = setup_regular()
    resp = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

def test_admin_users_no_auth():
    resp = client.get("/admin/users")
    assert resp.status_code == 401

def test_admin_list_users():
    aemail, atoken, auid = setup_admin()
    uemail, utoken, uuid = setup_regular()
    resp = client.get("/admin/users", headers={"Authorization": f"Bearer {atoken}"})
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1
    emails = [u["email"] for u in users]
    assert uemail in emails
    assert aemail not in emails

def test_admin_stats():
    email, token, uid = setup_admin()
    resp = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_users" in stats
    assert "total_api_requests" in stats
    assert stats["total_users"] >= 2

def test_admin_adjust_balance():
    email, token, uid = setup_admin()
    resp = client.post("/admin/users/adjust-balance", json={"user_id": uid, "amount": 25.0, "reason": "manual test"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["new_balance"] == 25.0

def test_admin_adjust_negative():
    email, token, uid = setup_admin()
    client.post("/admin/users/adjust-balance", json={"user_id": uid, "amount": 10.0, "reason": "add"}, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/admin/users/adjust-balance", json={"user_id": uid, "amount": -20.0, "reason": "subtract too much"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

def test_admin_suspend_user():
    aemail, atoken, auid = setup_admin()
    uemail, utoken, uuid = setup_regular()
    resp = client.post(f"/admin/users/{uuid}/suspend", json={"reason": "test"}, headers={"Authorization": f"Bearer {atoken}"})
    assert resp.status_code == 200
    suspended = client.post("/auth/login", json={"email": uemail, "password": "userpass123"})
    assert suspended.status_code == 403

def test_admin_activate_user():
    aemail, atoken, auid = setup_admin()
    uemail, utoken, uuuid = setup_regular()
    client.post(f"/admin/users/{uuuid}/suspend", json={"reason": "test"}, headers={"Authorization": f"Bearer {atoken}"})
    resp = client.post(f"/admin/users/{uuuid}/activate", headers={"Authorization": f"Bearer {atoken}"})
    assert resp.status_code == 200
    login = client.post("/auth/login", json={"email": uemail, "password": "userpass123"})
    assert login.status_code == 200

def test_admin_ledger():
    email, token, uid = setup_admin()
    client.post("/admin/users/adjust-balance", json={"user_id": uid, "amount": 5.0, "reason": "ledger test"}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/admin/ledger", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

def test_admin_cannot_suspend_admin():
    aemail, atoken, auid = setup_admin()
    resp = client.post(f"/admin/users/{auid}/suspend", json={"reason": "self"}, headers={"Authorization": f"Bearer {atoken}"})
    assert resp.status_code == 400