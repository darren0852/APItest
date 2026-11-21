"""Customer API Key management - platform-owned keys."""
import hashlib, secrets

class CustomerKeyManager:
    @staticmethod
    def generate_raw_key() -> tuple[str, str, str]:
        raw = f"sk-cust-{secrets.token_hex(24)}"
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        prefix = raw[:12]
        return raw, key_hash, prefix

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def verify_key(raw: str, stored_hash: str) -> bool:
        return hashlib.sha256(raw.encode()).hexdigest() == stored_hash

    @staticmethod
    def validate_format(key: str) -> bool:
        return key.startswith("sk-cust-") and len(key) >= 30

KEY_MANAGER = CustomerKeyManager()