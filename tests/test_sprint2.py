"""Sprint 2 tests: Registration, Login, API Key database management."""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)
import time; TEST_EMAIL = f"sprint2_test_{int(time.time())}@example.com"
TEST_PASS = "securepass123"

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200

def test_register_new_user():
    resp = client.post("/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["email"] == TEST_EMAIL

def test_register_duplicate():
    resp = client.post("/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert resp.status_code == 409

def test_register_bad_email():
    resp = client.post("/auth/register", json={"email": "notanemail", "password": TEST_PASS})
    assert resp.status_code == 400

def test_login_correct():
    resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert resp.status_code == 200
    assert "token" in resp.json()

def test_login_wrong_password():
    resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "wrongpass999"})
    assert resp.status_code == 401

def test_login_nonexistent():
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": TEST_PASS})
    assert resp.status_code == 401

def test_create_key_with_auth():
    login_resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    token = login_resp.json()["token"]
    resp = client.post("/me/api-keys", json={"name": "sprint2-key", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"].startswith("sk-cust-")

def test_create_key_no_auth():
    resp = client.post("/me/api-keys", json={"name": "unauth"})
    assert resp.status_code == 401

def test_list_keys():
    login_resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    token = login_resp.json()["token"]
    resp = client.get("/me/api-keys", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_revoke_key():
    login_resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    token = login_resp.json()["token"]
    create_resp = client.post("/me/api-keys", json={"name": "revoke-me", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    key_id = create_resp.json()["id"]
    resp = client.delete(f"/me/api-keys/{key_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    resp2 = client.delete(f"/me/api-keys/{key_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 404

def test_invalid_key_format_rejected():
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}, headers={"Authorization": "Bearer bad-key"})
    assert resp.status_code == 401

def test_random_key_format_rejected():
    fake = "sk-cust-" + "0" * 48
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}, headers={"Authorization": f"Bearer {fake}"})
    assert resp.status_code == 401

def test_chat_no_auth():
    resp = client.post("/v1/chat/completions", json={"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401
