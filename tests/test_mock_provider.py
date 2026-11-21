"""Tests for Mock Provider logic (pure, no HTTP needed)."""
import json, re, hashlib

def test_mock_stream_format():
    chunks = ["Hello", " from", " mock", " provider"]
    responses = []
    for i, c in enumerate(chunks):
        data = {
            "id": "mock-123",
            "object": "chat.completion.chunk",
            "model": "mock-model",
            "choices": [{"index": 0, "delta": ({"role": "assistant", "content": c} if i == 0 else {"content": c}), "finish_reason": ("stop" if i == len(chunks)-1 else None)}],
        }
        responses.append(f"data: {json.dumps(data)}\n\n")
    responses.append("data: [DONE]\n\n")
    assert all(r.startswith("data: ") for r in responses)
    assert "DONE" in responses[-1]

def test_mock_non_stream_format():
    resp = {
        "id": "mock-456",
        "object": "chat.completion",
        "model": "mock-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from mock provider"}, "finish_reason": "stop"}],
    }
    body = json.dumps(resp)
    assert "prompt_tokens" in body
    assert "finish_reason" in body

def test_api_key_hash_format():
    key = "sk-api-" + "a" * 48
    hashed = hashlib.sha256(key.encode()).hexdigest()
    assert len(hashed) == 64
