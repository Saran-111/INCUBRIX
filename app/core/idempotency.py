import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Optional
from app.connectors.base import Rendition, Destination

class IdempotencyRecord:
    def __init__(self, key: str, request_hash: str):
        self.key = key
        self.request_hash = request_hash
        self.status = "IN_PROGRESS"  # IN_PROGRESS, COMPLETED, FAILED
        self.response_data: Optional[Dict[str, Any]] = None
        self.response_status_code: int = 200
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None
        self.event: asyncio.Event = asyncio.Event()

def compute_request_hash(rendition: Rendition, destination: Destination, connector_key: Optional[str] = None) -> str:
    """
    Computes a canonical SHA-256 fingerprint of all fields that affect publishing,
    including title, body, tags, media, canonical URL, promo/AI metadata, and destination settings.
    """
    conn_key = connector_key or destination.connector_key or destination.platform_key
    canonical_dict = {
        "connector_key": conn_key,
        "destination_url": (destination.url or "").strip().lower().rstrip('/'),
        "surface": destination.surface,
        "custom_params": sorted(destination.custom_params.items()) if destination.custom_params else [],
        "title": (rendition.title or "").strip(),
        "body": rendition.body.strip(),
        "tags": sorted(rendition.tags or []),
        "media_urls": sorted(rendition.media_urls or []),
        "canonical_url": (rendition.canonical_url or "").strip(),
        "is_promotional": bool(rendition.is_promotional),
        "ai_generated": bool(rendition.ai_generated),
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

class IdempotencyStore:
    def __init__(self):
        self._records: Dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, key: str, request_hash: str) -> tuple[IdempotencyRecord, bool]:
        """
        Returns (record, is_new).
        If not new, caller must check if it's already completed or in progress.
        """
        async with self._lock:
            if key in self._records:
                return self._records[key], False
            record = IdempotencyRecord(key, request_hash)
            self._records[key] = record
            return record, True

    async def complete(self, key: str, response_data: Dict[str, Any], status_code: int = 200):
        async with self._lock:
            if key not in self._records:
                self._records[key] = IdempotencyRecord(key, "direct_complete")
            record = self._records[key]
            record.status = "COMPLETED"
            record.response_data = response_data
            record.response_status_code = status_code
            record.completed_at = time.time()
            record.event.set()

    async def fail(self, key: str, error_data: Dict[str, Any], status_code: int = 400):
        async with self._lock:
            if key not in self._records:
                self._records[key] = IdempotencyRecord(key, "direct_fail")
            record = self._records[key]
            record.status = "FAILED"
            record.response_data = error_data
            record.response_status_code = status_code
            record.completed_at = time.time()
            record.event.set()

    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        async with self._lock:
            return self._records.get(key)

idempotency_store = IdempotencyStore()
