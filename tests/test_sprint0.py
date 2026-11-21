"""Tests for Sprint 0 skeleton."""
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200

def test_register():
    resp = client.post("/auth/register", json={"email": f"s0_{int(time.time())}@test.com", "password": "testpass123"})
    assert resp.status_code == 200

def test_register_short_password():
    resp = client.post("/auth/register", json={"email": f"s0b_{int(time.time())}@test.com", "password": "short"})
    assert resp.status_code == 400

def test_api_key_requires_auth():
    resp = client.post("/me/api-keys", json={"name": "test", "group_name": "DeepSeek"})
    assert resp.status_code == 401