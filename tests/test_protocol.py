import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from protocol import (
    anthropic_event_to_openai_chunks,
    normalize_messages_for_protocol,
    to_anthropic_messages,
    to_openai_messages,
)


def test_anthropic_tool_use_becomes_openai_tool_calls():
    messages = [
        {"role": "user", "content": "weather"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "KL"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "31C"},
            ],
        },
    ]
    normalized = normalize_messages_for_protocol(messages, "openai")
    assert normalized[1]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert normalized[2]["role"] == "tool"
    assert normalized[2]["tool_call_id"] == "toolu_1"


def test_openai_tool_calls_become_anthropic_tool_blocks():
    messages = [
        {"role": "system", "content": "use tools"},
        {"role": "user", "content": "weather"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city":"KL"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "31C"},
    ]
    normalized = normalize_messages_for_protocol(messages, "anthropic")
    assert normalized[2]["content"][0]["type"] == "tool_use"
    assert normalized[3]["content"][0]["type"] == "tool_result"


def test_anthropic_stream_event_maps_to_openai_chunk():
    event = {
        "type": "message_delta",
        "id": "msg_1",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    chunks = anthropic_event_to_openai_chunks(event, "demo-model")
    assert chunks[0]["choices"][0]["finish_reason"] == "stop"
    assert chunks[0]["usage"]["prompt_tokens"] == 10
    assert chunks[0]["usage"]["completion_tokens"] == 5


def test_openai_text_content_survives_normalization():
    messages = [{"role": "user", "content": "hello"}]
    assert to_openai_messages(messages) == messages
    assert to_anthropic_messages(messages) == [{"role": "user", "content": "hello"}]
