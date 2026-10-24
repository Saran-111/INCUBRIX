from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Rendition(BaseModel):
    title: Optional[str] = ""
    body: str
    media_urls: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    canonical_url: Optional[str] = None
    is_promotional: bool = False
    ai_generated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Destination(BaseModel):
    name: str
    url: str
    platform_key: str
    surface: str = "default"
    category: Optional[str] = "general"
    audience_tags: List[str] = Field(default_factory=list)
    language: str = "en"
    geo: str = "global"
    est_audience: int = 0
    rules_url: Optional[str] = None
    frequency_cap: Optional[str] = "1/24h"  # e.g., "1/24h", "1/7d"
    self_promo_allowed: bool = True
    link_policy: str = "allowed"  # "allowed", "restricted", "banned"
    disclosure_required: bool = False
    automation_allowed: bool = True
    connector_key: str
    relevance_score: Optional[int] = 3
    relevance_reason: Optional[str] = None
    level: str = "L3"  # L0, L1, L2, L3, L4
    last_certified_at: Optional[str] = None
    custom_params: Dict[str, Any] = Field(default_factory=dict)

class Connection(BaseModel):
    auth_type: str = "none"  # api_key, oauth2, bot_token, hmac, none
    api_key: Optional[str] = None
    token: Optional[str] = None
    secret: Optional[str] = None
    base_url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    expires_at: Optional[str] = None

class Violation(BaseModel):
    field: str
    reason: str
    rule_type: str = "spec"  # "spec" or "policy"

class ValidationResult(BaseModel):
    ok: bool
    violations: List[Violation] = Field(default_factory=list)

class PublishResult(BaseModel):
    platform_post_id: str
    live_url: str
    status: str = "published"  # "published", "pending", "scheduled"

class StatusResult(BaseModel):
    status: str  # "live", "pending", "deleted", "rejected"
    live_url: Optional[str] = None

class DeleteResult(BaseModel):
    deleted: bool

class MetricsResult(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    watch_time_s: int = 0
    clicks: int = 0

class AssistFile(BaseModel):
    url: str
    type: str
    filename: str

class ChecklistItem(BaseModel):
    task: str
    checked: bool = False

class AssistPackResult(BaseModel):
    files: List[AssistFile] = Field(default_factory=list)
    caption: str
    deep_link: str
    checklist: List[ChecklistItem] = Field(default_factory=list)

class RefreshAuthResult(BaseModel):
    expires_at: str

class BaseConnector(ABC):
    def __init__(self, key: str, manifest_data: Dict[str, Any]):
        self.key = key
        self.manifest_data = manifest_data

    @abstractmethod
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        pass

    @abstractmethod
    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        pass

    @abstractmethod
    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        pass

    @abstractmethod
    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        pass

    async def fetch_metrics(self, platform_post_id: str, connection: Connection, since: Optional[str] = None) -> MetricsResult:
        raise NotImplementedError(f"Metrics not supported by connector {self.key}")

    async def refresh_auth(self, connection: Connection) -> RefreshAuthResult:
        raise NotImplementedError(f"Refresh auth not supported by connector {self.key}")

    async def build_assist_pack(self, rendition: Rendition, destination: Destination) -> AssistPackResult:
        raise NotImplementedError(f"Assist pack not supported by connector {self.key}")
