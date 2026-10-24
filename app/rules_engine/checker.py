import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from app.connectors.base import Rendition, Destination
from app.core.errors import ErrorCodes, IncubrixAPIException

class RuleCheckResult:
    def __init__(self, passed: bool, violations: List[Dict[str, str]], reschedule_at: Optional[str] = None):
        self.passed = passed
        self.violations = violations
        self.reschedule_at = reschedule_at

    def to_dict(self):
        return {
            "passed": self.passed,
            "violations": self.violations,
            "reschedule_at": self.reschedule_at
        }

class PostingRulesEngine:
    def __init__(self):
        # Maps destination_key/url -> list of post timestamps (epoch float)
        self._post_history: Dict[str, List[float]] = {}

    def record_post(self, destination_key: str, timestamp: Optional[float] = None):
        if timestamp is None:
            timestamp = time.time()
        if destination_key not in self._post_history:
            self._post_history[destination_key] = []
        self._post_history[destination_key].append(timestamp)

    def parse_frequency_cap(self, cap_str: Optional[str]) -> Tuple[int, int]:
        """
        Parses strings like '1/24h', '1/7d', '2/12h', '1/1w'.
        Returns (max_posts, window_seconds).
        """
        if not cap_str:
            return (1, 86400)  # Default 1 per 24 hours
        
        match = re.match(r"^(\d+)/(\d+)([hdw])$", cap_str.strip().lower())
        if not match:
            # Fallback
            return (1, 86400)
            
        count = int(match.group(1))
        unit_val = int(match.group(2))
        unit_char = match.group(3)
        
        if unit_char == 'h':
            window = unit_val * 3600
        elif unit_char == 'd':
            window = unit_val * 86400
        elif unit_char == 'w':
            window = unit_val * 7 * 86400
        else:
            window = 86400
            
        return (count, window)

    def check_rules(self, rendition: Rendition, destination: Destination) -> RuleCheckResult:
        violations: List[Dict[str, str]] = []
        reschedule_at: Optional[str] = None
        now = time.time()

        # 1. Frequency Cap Check
        dest_key = destination.url or destination.name
        max_posts, window_seconds = self.parse_frequency_cap(destination.frequency_cap)
        
        history = self._post_history.get(dest_key, [])
        # Filter posts within the window
        recent_posts = [ts for ts in history if (now - ts) < window_seconds]
        
        if len(recent_posts) >= max_posts:
            oldest_relevant_post = min(recent_posts)
            available_time = oldest_relevant_post + window_seconds
            wait_seconds = max(0, int(available_time - now))
            reschedule_dt = datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)
            reschedule_at = reschedule_dt.isoformat()
            
            violations.append({
                "rule": "FREQUENCY_CAP",
                "message": f"Destination frequency cap of {destination.frequency_cap} reached. A previous post occurred within the cooldown window.",
                "retry_after_seconds": str(wait_seconds),
                "reschedule_at": reschedule_at
            })

        # 2. Self-Promotion Policy
        if not destination.self_promo_allowed:
            promo_signals = [
                "buy now", "discount", "limited offer", "coupon", "sign up today",
                "promo code", "affiliate", "pricing", "free trial", "subscribe now"
            ]
            content_lower = f"{rendition.title or ''} {rendition.body}".lower()
            contains_promo_text = any(sig in content_lower for sig in promo_signals)
            
            if rendition.is_promotional or contains_promo_text:
                violations.append({
                    "rule": "SELF_PROMOTION_BANNED",
                    "message": f"Community '{destination.name}' strictly bans promotional content, product pitches, or commercial offers."
                })

        # 3. Link Policy
        content_links = re.findall(r'https?://[^\s]+', rendition.body)
        if destination.link_policy == "banned" and content_links:
            violations.append({
                "rule": "LINKS_BANNED",
                "message": f"Community '{destination.name}' bans external links in post body. Found {len(content_links)} links."
            })

        # 4. AI-Content Disclosure Policy
        if destination.disclosure_required:
            disclosure_patterns = [
                "disclosure:", "ai generated", "generated with ai",
                "assistance of ai", "ai-assisted", "ai disclosure"
            ]
            has_disclosure = any(pat in rendition.body.lower() for pat in disclosure_patterns)
            
            if rendition.ai_generated and not has_disclosure:
                violations.append({
                    "rule": "AI_DISCLOSURE_REQUIRED",
                    "message": f"Community '{destination.name}' requires explicit disclosure for AI-generated or AI-assisted content."
                })

        # 5. Automation Policy
        if not destination.automation_allowed and destination.connector_key != "assisted":
            violations.append({
                "rule": "AUTOMATION_PROHIBITED",
                "message": f"Community '{destination.name}' prohibits automated API posting. Posts must use the assisted connector for manual submission."
            })

        return RuleCheckResult(
            passed=len(violations) == 0,
            violations=violations,
            reschedule_at=reschedule_at
        )

rules_engine = PostingRulesEngine()
