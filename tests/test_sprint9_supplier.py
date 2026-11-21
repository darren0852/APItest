import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from fastapi.testclient import TestClient

from supplier import get_supplier_route
from supplier_crypto import decrypt_secret

from main import app


client = TestClient(app)


def setup_user():
    import uuid
    email = f"supplier-{uuid.uuid4().hex[:10]}@example.test"
    response = client.post("/auth/register", json={"email": email, "password": "Suppl1erPass"})
    assert response.status_code == 200
    token = response.json()["token"]
    topup = client.post("/billing/topups", json={"amount": 10}, headers={"Authorization": f"Bearer {token}"})
    assert topup.status_code == 200
    key = client.post("/me/api-keys", json={"name": "supplier-test", "group_name": "DeepSeek"}, headers={"Authorization": f"Bearer {token}"})
    assert key.status_code == 200
    return key.json()["key"]


def test_supplier_route_supports_end_to_end_proxy():
    from database import SessionLocal
    route = get_supplier_route(SessionLocal(), "mock-model")
    assert route is not None
    assert route.endpoint_url == "http://localhost:9000/v1/chat/completions"
    assert decrypt_secret(route.api_key_encrypted) == "mock-key-internal"

    raw_key = setup_user()
    response = client.post(
        "/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "supplier route test"}]},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "mock-model"
    assert body["choices"][0]["message"]["content"].startswith("Hello from mock provider")

    from database import SessionLocal
    session = SessionLocal()
    refreshed = get_supplier_route(session, "mock-model")
    session.close()
    assert refreshed is not None
    assert refreshed.key_status == "healthy"
