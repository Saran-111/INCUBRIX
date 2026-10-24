from typing import Any, Dict, Optional
from fastapi import APIRouter, Body
from pydantic import BaseModel
from app.connectors.base import Rendition, Destination
from app.rules_engine.checker import rules_engine
from app.rules_engine.ai_extractor import rules_extractor, confirmation_store, ProposedRules
from app.core.errors import ErrorCodes, IncubrixAPIException

router = APIRouter(prefix="/api/v1/rules", tags=["Rules Engine"])

class RuleCheckPayload(BaseModel):
    rendition: Rendition
    destination: Destination

class ExtractRulesPayload(BaseModel):
    community_name: str
    rules_text: str
    rules_url: Optional[str] = None

class ConfirmRulesPayload(BaseModel):
    proposal_id: str
    overrides: Optional[Dict[str, Any]] = None

@router.post("/check")
async def check_posting_rules(payload: RuleCheckPayload):
    """
    Must-have 4: Rules checked before every post: frequency cap,
    self-promotion policy, link policy and AI-content disclosure.
    """
    result = rules_engine.check_rules(payload.rendition, payload.destination)
    if not result.passed:
        # Check if due to frequency cap
        has_freq_cap = any(v.get("rule") == "FREQUENCY_CAP" for v in result.violations)
        code = ErrorCodes.DEST_RULE_FREQUENCY_CAP if has_freq_cap else ErrorCodes.DEST_SPEC_VIOLATION
        
        return {
            "passed": False,
            "error": {
                "code": code,
                "message": "Post blocked by destination rules engine.",
                "retryable": has_freq_cap,
                "details": result.violations,
                "reschedule_at": result.reschedule_at
            }
        }
    return {"passed": True, "violations": []}

@router.post("/extract", response_model=ProposedRules)
async def extract_rules_from_community(payload: ExtractRulesPayload):
    """
    Advanced Level: AI step reads a community's rules page and proposes its posting rules.
    """
    proposal = await rules_extractor.extract_rules_from_text(
        payload.community_name,
        payload.rules_text,
        payload.rules_url
    )
    confirmation_store.save(proposal)
    return proposal

@router.post("/confirm", response_model=ProposedRules)
async def confirm_rules(payload: ConfirmRulesPayload):
    """
    Advanced Level: Human confirms or modifies rules before they are committed to catalogue.
    """
    try:
        confirmed = confirmation_store.confirm(payload.proposal_id, payload.overrides)
        return confirmed
    except KeyError:
        raise IncubrixAPIException(
            code=ErrorCodes.INVALID_PAYLOAD,
            message=f"Proposal '{payload.proposal_id}' not found.",
            status_code=404
        )
