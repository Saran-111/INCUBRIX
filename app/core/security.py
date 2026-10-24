import hashlib
import hmac
import json
from typing import Any, Dict
from app.core.config import settings

def generate_hmac_signature(payload: bytes, secret: str = settings.HMAC_SECRET) -> str:
    """Computes HMAC-SHA256 signature encoded as hex string."""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

def verify_hmac_signature(payload: bytes, signature: str, secret: str = settings.HMAC_SECRET) -> bool:
    """Verifies HMAC-SHA256 signature in constant time."""
    expected = generate_hmac_signature(payload, secret)
    return hmac.compare_digest(expected, signature)

def sign_json_payload(data: Dict[str, Any], secret: str = settings.HMAC_SECRET) -> tuple[str, str]:
    """Serializes JSON and returns (json_string, hex_signature)."""
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    sig = generate_hmac_signature(serialized.encode("utf-8"), secret)
    return serialized, sig
