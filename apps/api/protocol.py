import json
import uuid
from typing import Any, Iterable


def _flatten_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            block_type = str(item.get("type", ""))
            if block_type in {"text", "input_text", "output_text"}:
                parts.append(str(item.get("text", "")))
            elif block_type == "tool_result":
                parts.append(_flatten_text(item.get("content", "")))
            elif block_type == "tool_use":
                parts.append(
                    json.dumps(
                        {"name": item.get("name", ""), "input": item.get("input", {})},
                        ensure_ascii=False,
                    )
                )
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _safe_json(value: Any) -> Any:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return str(value)


def to_openai_messages(messages: Iterable[Any]) -> list[dict]:
    result: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, list):
            if role == "assistant":
                text_parts: list[str] = []
                tool_calls = list(message.get("tool_calls") or [])
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = str(block.get("type", ""))
                    if block_type in {"text", "input_text", "output_text"}:
                        text_parts.append(str(block.get("text", "")))
                    elif block_type == "tool_use":
                        tool_calls.append(
                            {
                                "id": block.get("id") or f"call_{uuid.uuid4().hex[:16]}",
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                                },
                            }
                        )
                normalized_content = "\n".join(part for part in text_parts if part)
                normalized = {"role": "assistant", "content": normalized_content}
                if tool_calls:
                    normalized["tool_calls"] = tool_calls
                result.append(normalized)
                continue
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id")
                            or block.get("tool_call_id")
                            or "",
                            "content": _flatten_text(block.get("content", "")),
                        }
                    )
                elif block is not None:
                    text_parts.append(_flatten_text(block))
            text = "\n".join(part for part in text_parts if part)
            if text:
                result.append({"role": role, "content": text})
            continue
        normalized = {"role": role, "content": content if content is not None else ""}
        if role == "assistant" and message.get("tool_calls"):
            normalized["tool_calls"] = message["tool_calls"]
        result.append(normalized)
    return result


def to_anthropic_messages(messages: Iterable[Any]) -> list[dict]:
    result: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if role == "tool":
            result.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.get("tool_call_id") or message.get("id") or "",
                            "content": _flatten_text(message.get("content", "")),
                        }
                    ],
                }
            )
            continue
        if role == "assistant":
            blocks: list[dict] = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = str(block.get("type", ""))
                    if block_type in {"text", "input_text", "output_text"}:
                        blocks.append({"type": "text", "text": str(block.get("text", ""))})
                    elif block_type == "tool_use":
                        blocks.append(block)
            for tool_call in message.get("tool_calls") or []:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function") or {}
                arguments = function.get("arguments", "{}")
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
                        "name": function.get("name", ""),
                        "input": arguments
                        if isinstance(arguments, dict)
                        else _safe_json(arguments),
                    }
                )
            result.append({"role": "assistant", "content": blocks or ""})
            continue
        if role == "system":
            result.append({"role": "system", "content": content if content is not None else ""})
            continue
        if isinstance(content, list):
            blocks = []
            for block in content:
                if not isinstance(block, dict):
                    blocks.append({"type": "text", "text": str(block)})
                    continue
                block_type = str(block.get("type", ""))
                if block_type in {"text", "input_text", "output_text"}:
                    blocks.append({"type": "text", "text": str(block.get("text", ""))})
                elif block_type in {"tool_result", "tool_use", "image"}:
                    blocks.append(block)
                else:
                    blocks.append({"type": "text", "text": _flatten_text(block)})
            result.append({"role": "user", "content": blocks or ""})
            continue
        result.append({"role": "user", "content": content if content is not None else ""})
    return result


def normalize_messages_for_protocol(messages: Iterable[Any], protocol: str) -> list[dict]:
    if protocol == "anthropic":
        return to_anthropic_messages(messages)
    return to_openai_messages(messages)


def anthropic_event_to_openai_chunks(event: Any, model: str = "") -> list[dict]:
    """Bridge Anthropic SSE events into OpenAI-compatible stream chunks.

    The helper intentionally performs no I/O so the mapping can be tested
    independently from any supplier connection.
    """
    if not isinstance(event, dict):
        return []
    chunks: list[dict] = []
    event_type = event.get("type")
    chunk_id = event.get("id") or f"chatcmpl_{uuid.uuid4().hex[:24]}"
    if event_type == "message_start":
        usage = (event.get("message") or {}).get("usage") or {}
        if usage:
            input_tokens = int(usage.get("input_tokens") or 0)
            cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
            cache_write_tokens = int(usage.get("cache_creation_input_tokens") or 0)
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": 0,
                        "total_tokens": input_tokens,
                        "prompt_tokens_details": {
                            "cached_tokens": cache_read_tokens,
                            "cache_creation_input_tokens": cache_write_tokens,
                        },
                    },
                }
            )
    elif event_type == "content_block_delta":
        delta = event.get("delta") or {}
        text = delta.get("text") or delta.get("thinking") or ""
        if text:
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": str(text)}, "finish_reason": None}],
                }
            )
    elif event_type == "message_delta":
        usage = event.get("usage") or {}
        stop_reason = (event.get("delta") or {}).get("stop_reason")
        finish_reason = {
            "end_turn": "stop",
            "stop": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
        }.get(stop_reason, stop_reason) or "stop"
        if usage:
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
            cache_write_tokens = int(usage.get("cache_creation_input_tokens") or 0)
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [
                        {"index": 0, "delta": {}, "finish_reason": finish_reason}
                    ],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                        "prompt_tokens_details": {
                            "cached_tokens": cache_read_tokens,
                            "cache_creation_input_tokens": cache_write_tokens,
                        },
                    },
                }
            )
    elif event_type == "error":
        chunks.append({"error": {"message": str((event.get("error") or {}).get("message", "Supplier error"))[:400]}})
    return chunks
