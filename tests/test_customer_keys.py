"""Tests for Customer Key management."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from customer_keys import KEY_MANAGER, CustomerKeyManager

def test_generate_key():
    raw, key_hash, prefix = KEY_MANAGER.generate_raw_key()
    assert raw.startswith("sk-cust-")
    assert len(raw) >= 40
    assert len(key_hash) == 64
    assert len(prefix) == 12

def test_key_hash_matches():
    raw, key_hash, _ = KEY_MANAGER.generate_raw_key()
    assert KEY_MANAGER.verify_key(raw, key_hash)

def test_key_hash_no_mismatch():
    raw1, h1, _ = KEY_MANAGER.generate_raw_key()
    raw2, _, _ = KEY_MANAGER.generate_raw_key()
    assert not KEY_MANAGER.verify_key(raw2, h1)

def test_key_format():
    raw, _, _ = KEY_MANAGER.generate_raw_key()
    assert KEY_MANAGER.validate_format(raw)
    assert not KEY_MANAGER.validate_format("bad-key")
    assert not KEY_MANAGER.validate_format("sk-openai-real-key")

def test_two_keys_different():
    raw1, h1, p1 = KEY_MANAGER.generate_raw_key()
    raw2, h2, p2 = KEY_MANAGER.generate_raw_key()
    assert raw1 != raw2
    assert h1 != h2
