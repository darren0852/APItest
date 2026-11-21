"""Pytest configuration: dedicated test database + app startup."""
import os, sys

os.environ["DB_NAME"] = "apiplatform_test"
os.environ["DB_USER"] = "apidev"
os.environ["DB_PASS"] = "apidev123"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DATABASE_URL"] = "postgresql://apidev:apidev123@localhost:5432/apiplatform_test"
os.environ["ENABLE_INTERNAL_MOCK"] = "true"
os.environ["JWT_SECRET"] = "test-only-jwt-secret"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps", "api"))

import pytest

@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    from database import init_db
    init_db()
    import main
    main.seed_plans()
    main.seed_model_prices()
    main.seed_internal_supplier()
