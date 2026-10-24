import asyncio
import time
from typing import Any, Dict, Optional

class IdempotencyRecord:
    def __init__(self, key: str, request_hash: str):
        self.key = key
        self.request_hash = request_hash
        self.status = "IN_PROGRESS"  # IN_PROGRESS, COMPLETED, FAILED
        self.response_data: Optional[Dict[str, Any]] = None
        self.response_status_code: int = 200
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None

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
            self._records[key].status = "COMPLETED"
            self._records[key].response_data = response_data
            self._records[key].response_status_code = status_code
            self._records[key].completed_at = time.time()

    async def fail(self, key: str, error_data: Dict[str, Any], status_code: int = 400):
        async with self._lock:
            if key not in self._records:
                self._records[key] = IdempotencyRecord(key, "direct_fail")
            self._records[key].status = "FAILED"
            self._records[key].response_data = error_data
            self._records[key].response_status_code = status_code
            self._records[key].completed_at = time.time()

    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        async with self._lock:
            return self._records.get(key)

idempotency_store = IdempotencyStore()
