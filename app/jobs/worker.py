import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional
import httpx
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging import logger
from app.core.security import sign_json_payload

class OutputManifest(BaseModel):
    version: str = "1.0.0"
    service: str = settings.APP_NAME
    providers_used: Dict[str, str] = Field(default_factory=lambda: {"connector_runtime": "native_python_3.13", "ai_heuristics": "local_nlp"})
    settings: Dict[str, Any] = Field(default_factory=dict)
    seed: int = 42
    timings: Dict[str, float] = Field(default_factory=dict)
    cost_estimate_usd: float = 0.0000
    warnings: list[str] = Field(default_factory=list)
    licence: str = "Apache-2.0 / Commercial Compatible"
    rights_information: str = "Candidate proprietary code submitted to IncuBrix assessment evaluation."

class Job(BaseModel):
    job_id: str
    idempotency_key: Optional[str] = None
    status: str = "queued"  # queued, running, succeeded, failed
    progress: int = 0  # 0 to 100
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    result_url: Optional[str] = None
    manifest: Optional[OutputManifest] = None
    error: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None

class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, idempotency_key: Optional[str] = None, callback_url: Optional[str] = None) -> Job:
        async with self._lock:
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            job = Job(
                job_id=job_id,
                idempotency_key=idempotency_key,
                status="queued",
                progress=0,
                created_at=datetime.now(timezone.utc).isoformat(),
                callback_url=callback_url
            )
            self._jobs[job_id] = job
            return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_progress(self, job_id: str, progress: int, status: str = "running"):
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = min(100, max(0, progress))
                self._jobs[job_id].status = status
                if not self._jobs[job_id].started_at:
                    self._jobs[job_id].started_at = datetime.now(timezone.utc).isoformat()

    async def succeed_job(
        self,
        job_id: str,
        result: Dict[str, Any],
        manifest: Optional[OutputManifest] = None,
        result_url: Optional[str] = None
    ):
        job = None
        async with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "succeeded"
                job.progress = 100
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.result = result
                job.result_url = result_url
                job.manifest = manifest or OutputManifest()
        
        if job and job.callback_url:
            await self._dispatch_callback(job)

    async def fail_job(self, job_id: str, error_dict: Dict[str, Any]):
        job = None
        async with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.error = error_dict
        
        if job and job.callback_url:
            await self._dispatch_callback(job)

    async def _dispatch_callback(self, job: Job):
        """Sends signed HMAC callback to user specified webhook URL."""
        try:
            payload = job.model_dump()
            serialized, signature = sign_json_payload(payload, settings.HMAC_SECRET)
            headers = {
                "Content-Type": "application/json",
                settings.WEBHOOK_SIGNATURE_HEADER: signature
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(job.callback_url, content=serialized, headers=headers)
                logger.info(f"Dispatched signed webhook callback for job {job.job_id} to {job.callback_url}")
        except Exception as e:
            logger.warning(f"Failed to deliver callback for job {job.job_id}: {str(e)}")

job_manager = JobManager()
