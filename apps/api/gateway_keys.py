"""Gateway auth middleware - validates Customer Keys before proxying."""
import hashlib
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from customer_keys import KEY_MANAGER

router = APIRouter(prefix="/gateway", tags=["gateway"])

class KeyCreate(BaseModel):
    name: str = "default"
    allowed_models: list[str] | None = None
    rpm_limit: int | None = None

@router.post("/keys")
async def create_customer_key(req: KeyCreate):
    raw, key_hash, prefix = KEY_MANAGER.generate_raw_key()
    return {"key": raw, "key_hash": key_hash, "prefix": prefix, "name": req.name}

@router.post("/keys/verify")
async def verify_customer_key(key: str):
    if not KEY_MANAGER.validate_format(key):
        return {"valid": False, "reason": "invalid_format"}
    return {"valid": True, "reason": "format_ok"}
