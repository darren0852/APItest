import time
import uuid

import httpx
from sqlalchemy.orm import Session

from pricing import Supplier, SupplierRoute
from protocol import normalize_messages_for_protocol
from supplier_crypto import decrypt_secret


class SupplierRequestError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_supplier_route(db: Session, model_name: str) -> SupplierRoute | None:
    return (
        db.query(SupplierRoute)
        .join(Supplier, Supplier.id == SupplierRoute.supplier_id)
        .filter(
            SupplierRoute.model_name == model_name,
            SupplierRoute.status == "active",
            Supplier.status == "active",
        )
        .order_by(SupplierRoute.priority, Supplier.id)
        .first()
    )


OPENAI_EXTRA_KEYS = ("tools", "tool_choice", "temperature", "top_p", "frequency_penalty", "presence_penalty")


def build_openai_payload(platform_model: str, route: SupplierRoute, messages: list, stream: bool, extra_body: dict = None) -> dict:
    payload = {"model": route.upstream_model, "messages": messages, "stream": stream}
    if extra_body:
        for key in OPENAI_EXTRA_KEYS:
            value = extra_body.get(key)
            if value is not None:
                payload[key] = value
    return payload


def build_anthropic_payload(platform_model: str, route: SupplierRoute, messages: list, stream: bool, extra_body: dict = None) -> dict:
    system_parts = []
    chat_messages = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system":
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        system_parts.append(str(block.get("text", "")))
                    else:
                        system_parts.append(str(block))
            else:
                system_parts.append(str(content))
        else:
            chat_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    payload = {
        "model": route.upstream_model,
        "messages": chat_messages,
        "max_tokens": (extra_body.get("max_tokens") or 4096) if extra_body else 4096,
        "stream": stream,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    if extra_body:
        for key in ("tools", "tool_choice", "temperature", "top_p"):
            value = extra_body.get(key)
            if value is not None:
                payload[key] = value
    return payload


def upstream_request(route: SupplierRoute, messages: list, stream: bool = False, extra_body: dict = None) -> tuple[dict, dict, dict]:
    api_key = decrypt_secret(route.api_key_encrypted)
    messages = normalize_messages_for_protocol(messages, route.protocol)
    if route.protocol == "anthropic":
        headers = {
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = build_anthropic_payload(route.model_name, route, messages, stream, extra_body)
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = build_openai_payload(route.model_name, route, messages, stream, extra_body)
    return route.endpoint_url, headers, payload


def normalize_anthropic_response(platform_model: str, response: dict) -> dict:
    blocks = response.get("content", [])
    content = "".join(block.get("text", "") for block in blocks if isinstance(block, dict))
    usage = response.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
    cache_write_tokens = usage.get("cache_creation_input_tokens", 0) or 0
    cached_tokens = cache_read_tokens
    if cached_tokens:
        input_tokens += cached_tokens
    if cache_write_tokens:
        input_tokens += cache_write_tokens
    return {
        "id": response.get("id") or str(uuid.uuid4()),
        "created": int(time.time()),
        "model": platform_model,
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop" if response.get("stop_reason") in (None, "end_turn", "stop") else response.get("stop_reason"),
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "prompt_tokens_details": {
                "cached_tokens": cached_tokens,
                "cache_creation_input_tokens": cache_write_tokens,
            },
            "cache_creation_input_tokens": cache_write_tokens,
        },
    }
