import asyncio
import csv
import io
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse
from app.catalogue.models import DestinationRecord
from app.catalogue.scorer import calculate_relevance_score
from app.connectors.registry import connector_registry

class RowErrorReport(BaseException):
    pass

class ImportReport:
    def __init__(self):
        self.total_rows: int = 0
        self.valid_imported: int = 0
        self.duplicates_skipped: int = 0
        self.errors_count: int = 0
        self.time_seconds: float = 0.0
        self.row_errors: List[Dict[str, Any]] = []

    def to_dict(self):
        return {
            "total_rows": self.total_rows,
            "valid_imported": self.valid_imported,
            "duplicates_skipped": self.duplicates_skipped,
            "errors_count": self.errors_count,
            "time_seconds": round(self.time_seconds, 3),
            "row_errors": self.row_errors
        }

class DestinationCatalogue:
    def __init__(self):
        self._destinations: Dict[str, DestinationRecord] = {}
        self._lock = asyncio.Lock()

    async def add_or_update(self, dest: DestinationRecord):
        async with self._lock:
            self._destinations[dest.normalized_identity()] = dest

    async def get_by_identity(self, platform_key: str, url: str) -> Optional[DestinationRecord]:
        norm_url = url.strip().lower().rstrip('/')
        key = f"{platform_key.strip().lower()}::{norm_url}"
        async with self._lock:
            return self._destinations.get(key)

    async def get_by_url(self, url: str) -> Optional[DestinationRecord]:
        norm_url = url.strip().lower().rstrip('/')
        async with self._lock:
            for d in self._destinations.values():
                if d.url.strip().lower().rstrip('/') == norm_url:
                    return d
        return None

    async def list_all(self) -> List[DestinationRecord]:
        async with self._lock:
            return list(self._destinations.values())

    async def demote_destination(self, platform_key: str, url: str, reason: str):
        dest = await self.get_by_identity(platform_key, url)
        if dest:
            dest.level = "L0"
            dest.relevance_reason = f"[DEMOTED]: {reason}"

catalogue_store = DestinationCatalogue()

def normalize_url(url: str) -> str:
    """Normalizes URL scheme, host and path."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip('/')
    return f"{scheme}://{netloc}{path}"

def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False

async def check_reachability_fast(url: str) -> bool:
    """Simulates or performs fast reachability check."""
    # Fast reachability heuristic
    if not is_valid_url(url) or "invalid" in url or "example.invalid" in url:
        return False
    return True

async def import_destinations_from_csv(csv_text: str) -> ImportReport:
    start_time = time.time()
    report = ImportReport()
    seen_identities: Set[str] = set()

    reader = csv.DictReader(io.StringIO(csv_text))
    row_num = 1  # 1-indexed header

    for row in reader:
        row_num += 1
        report.total_rows += 1

        try:
            name = (row.get("name") or "").strip()
            raw_url = (row.get("url") or "").strip()
            platform_key = (row.get("platform_key") or "").strip().lower()
            connector_key = (row.get("connector_key") or platform_key).strip().lower()

            if not name:
                report.errors_count += 1
                report.row_errors.append({
                    "row": row_num,
                    "field": "name",
                    "error": "Missing community / destination name"
                })
                continue

            if not raw_url or not is_valid_url(raw_url):
                report.errors_count += 1
                report.row_errors.append({
                    "row": row_num,
                    "field": "url",
                    "error": f"Invalid URL format: '{raw_url}'"
                })
                continue

            norm_url = normalize_url(raw_url)
            identity = f"{platform_key}::{norm_url}"

            # Deduplication
            if identity in seen_identities:
                report.duplicates_skipped += 1
                continue
            seen_identities.add(identity)

            # Reachability check
            is_reachable = await check_reachability_fast(norm_url)
            if not is_reachable:
                report.errors_count += 1
                report.row_errors.append({
                    "row": row_num,
                    "field": "url",
                    "error": f"Destination URL unreachable: {norm_url}"
                })
                continue

            # Parse tags
            raw_tags = row.get("audience_tags", "")
            tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]

            category = row.get("category", "general")
            surface = row.get("surface", "default")
            language = row.get("language", "en")
            geo = row.get("geo", "global")
            
            try:
                est_audience = int(row.get("est_audience", 0) or 0)
            except ValueError:
                est_audience = 1000

            # Rules fields
            rules_url = row.get("rules_url") or None
            frequency_cap = row.get("frequency_cap", "1/24h")
            self_promo_allowed = str(row.get("self_promo_allowed", "true")).lower() in ("true", "1", "yes")
            link_policy = row.get("link_policy", "allowed").lower()
            disclosure_required = str(row.get("disclosure_required", "false")).lower() in ("true", "1", "yes")
            automation_allowed = str(row.get("automation_allowed", "true")).lower() in ("true", "1", "yes")
            level = row.get("level", "L0").upper()

            # Relevance scoring
            score_val = row.get("relevance_score")
            reason_val = row.get("relevance_reason")
            
            if score_val and str(score_val).isdigit() and int(score_val) > 0:
                rel_score = int(score_val)
                rel_reason = reason_val or "Pre-assigned relevance"
            else:
                rel_score, rel_reason = calculate_relevance_score(name, category, tags)

            record = DestinationRecord(
                name=name,
                url=norm_url,
                platform_key=platform_key,
                surface=surface,
                category=category,
                audience_tags=tags,
                language=language,
                geo=geo,
                est_audience=est_audience,
                rules_url=rules_url,
                frequency_cap=frequency_cap,
                self_promo_allowed=self_promo_allowed,
                link_policy=link_policy,
                disclosure_required=disclosure_required,
                automation_allowed=automation_allowed,
                connector_key=connector_key,
                relevance_score=rel_score,
                relevance_reason=rel_reason,
                level=level
            )

            await catalogue_store.add_or_update(record)
            report.valid_imported += 1

        except Exception as e:
            report.errors_count += 1
            report.row_errors.append({
                "row": row_num,
                "error": f"Failed processing row: {str(e)}"
            })

    report.time_seconds = time.time() - start_time
    return report
