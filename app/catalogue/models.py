from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DestinationRecord(BaseModel):
    name: str
    url: str
    platform_key: str
    surface: str = "default"
    category: str = "technology"
    audience_tags: List[str] = Field(default_factory=list)
    language: str = "en"
    geo: str = "global"
    est_audience: int = 0
    rules_url: Optional[str] = None
    frequency_cap: str = "1/24h"
    self_promo_allowed: bool = True
    link_policy: str = "allowed"  # allowed, restricted, banned
    disclosure_required: bool = False
    automation_allowed: bool = True
    connector_key: str
    relevance_score: int = 3  # 1 to 5
    relevance_reason: str = "General developer and creator audience"
    level: str = "L0"  # L0, L1, L2, L3, L4
    last_certified_at: Optional[str] = None
    custom_params: Dict[str, Any] = Field(default_factory=dict)

    def normalized_identity(self) -> str:
        """Normalized URL + platform_key for deduplication."""
        norm_url = self.url.strip().lower().rstrip('/')
        return f"{self.platform_key.strip().lower()}::{norm_url}"
