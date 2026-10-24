import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ProposedRules(BaseModel):
    proposal_id: str
    community_name: str
    rules_url: Optional[str] = None
    frequency_cap: str = "1/24h"
    self_promo_allowed: bool = True
    link_policy: str = "allowed"  # allowed, restricted, banned
    disclosure_required: bool = False
    automation_allowed: bool = True
    reasoning: str
    status: str = "pending_confirmation"  # pending_confirmation, confirmed, rejected

class BaseRulesExtractor(ABC):
    @abstractmethod
    async def extract_rules_from_text(self, community_name: str, rules_text: str, rules_url: Optional[str] = None) -> ProposedRules:
        pass

class HeuristicMockRulesExtractor(BaseRulesExtractor):
    """
    High-fidelity offline heuristic extractor adhering to rule 3 (runs without external API keys).
    Detects standard community rule patterns.
    """
    async def extract_rules_from_text(self, community_name: str, rules_text: str, rules_url: Optional[str] = None) -> ProposedRules:
        text_lower = rules_text.lower()
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        
        # Analyze self promotion
        no_promo_patterns = [
            "no self-promotion", "no self promo", "no advertising", "no spam",
            "self-promotion is not allowed", "promotional posts will be removed",
            "no commercial"
        ]
        self_promo_allowed = not any(p in text_lower for p in no_promo_patterns)
        
        # Analyze link policy
        if "no links" in text_lower or "links are forbidden" in text_lower or "no external urls" in text_lower:
            link_policy = "banned"
        elif "links in comments only" in text_lower or "limit links" in text_lower or "restricted links" in text_lower:
            link_policy = "restricted"
        else:
            link_policy = "allowed"

        # Analyze AI disclosure
        disclosure_patterns = [
            "ai disclosure", "must disclose ai", "label ai content", "ai generated content must be disclosed",
            "disclose use of ai"
        ]
        disclosure_required = any(p in text_lower for p in disclosure_patterns)
        
        # Analyze automation
        automation_banned_patterns = [
            "no bots", "bots will be banned", "no automated posting", "manual posts only", "humans only"
        ]
        automation_allowed = not any(p in text_lower for p in automation_banned_patterns)

        # Analyze frequency cap
        freq_cap = "1/24h"
        if "once a week" in text_lower or "one post per week" in text_lower or "1 post every 7 days" in text_lower:
            freq_cap = "1/7d"
        elif "max 2 posts per day" in text_lower or "twice daily" in text_lower:
            freq_cap = "2/24h"
        elif "max 3 posts per day" in text_lower:
            freq_cap = "3/24h"

        reasons = []
        if not self_promo_allowed:
            reasons.append("Detected anti-advertising / self-promotion restrictions in community rules.")
        if link_policy != "allowed":
            reasons.append(f"Detected link constraints: policy set to {link_policy}.")
        if disclosure_required:
            reasons.append("Identified explicit requirement to disclose AI-assisted submissions.")
        if not automation_allowed:
            reasons.append("Automated API bots forbidden by community guidelines.")
        if not reasons:
            reasons.append("Standard community posting guidelines detected with default 24h frequency cap.")

        return ProposedRules(
            proposal_id=proposal_id,
            community_name=community_name,
            rules_url=rules_url,
            frequency_cap=freq_cap,
            self_promo_allowed=self_promo_allowed,
            link_policy=link_policy,
            disclosure_required=disclosure_required,
            automation_allowed=automation_allowed,
            reasoning="; ".join(reasons),
            status="pending_confirmation"
        )

class RulesConfirmationStore:
    def __init__(self):
        self.proposals: Dict[str, ProposedRules] = {}

    def save(self, proposal: ProposedRules):
        self.proposals[proposal.proposal_id] = proposal

    def get(self, proposal_id: str) -> Optional[ProposedRules]:
        return self.proposals.get(proposal_id)

    def confirm(self, proposal_id: str, overrides: Optional[Dict[str, Any]] = None) -> ProposedRules:
        prop = self.proposals.get(proposal_id)
        if not prop:
            raise KeyError(f"Proposal {proposal_id} not found")
        if overrides:
            for k, v in overrides.items():
                if hasattr(prop, k):
                    setattr(prop, k, v)
        prop.status = "confirmed"
        return prop

    def reject(self, proposal_id: str) -> ProposedRules:
        prop = self.proposals.get(proposal_id)
        if not prop:
            raise KeyError(f"Proposal {proposal_id} not found")
        prop.status = "rejected"
        return prop

rules_extractor: BaseRulesExtractor = HeuristicMockRulesExtractor()
confirmation_store = RulesConfirmationStore()
