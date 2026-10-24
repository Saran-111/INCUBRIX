from typing import Any, Dict, List
from app.connectors.base import Rendition, Destination, Violation, ValidationResult

def validate_rendition_against_spec(rendition: Rendition, spec: Dict[str, Any]) -> List[Violation]:
    violations: List[Violation] = []
    
    title = (rendition.title or "").strip()
    body = (rendition.body or "").strip()
    
    # Check title limits if defined
    if "title_min_chars" in spec and len(title) < spec["title_min_chars"]:
        violations.append(Violation(
            field="title",
            reason=f"Title is shorter than minimum required length of {spec['title_min_chars']} characters.",
            rule_type="spec"
        ))
    if "title_max_chars" in spec and len(title) > spec["title_max_chars"]:
        violations.append(Violation(
            field="title",
            reason=f"Title exceeds maximum permitted length of {spec['title_max_chars']} characters (got {len(title)}).",
            rule_type="spec"
        ))
        
    # Check body limits
    if "body_min_chars" in spec and len(body) < spec["body_min_chars"]:
        violations.append(Violation(
            field="body",
            reason=f"Body is shorter than minimum required length of {spec['body_min_chars']} characters.",
            rule_type="spec"
        ))
    if "body_max_chars" in spec and len(body) > spec["body_max_chars"]:
        violations.append(Violation(
            field="body",
            reason=f"Body exceeds maximum permitted length of {spec['body_max_chars']} characters (got {len(body)}).",
            rule_type="spec"
        ))
        
    # Check tags limits
    if "max_tags" in spec and len(rendition.tags) > spec["max_tags"]:
        violations.append(Violation(
            field="tags",
            reason=f"Tags count ({len(rendition.tags)}) exceeds allowed maximum of {spec['max_tags']}.",
            rule_type="spec"
        ))
        
    # Check link allowance
    if spec.get("links_allowed") is False:
        if "http://" in body.lower() or "https://" in body.lower():
            violations.append(Violation(
                field="body",
                reason="Hyperlinks are strictly prohibited on this surface.",
                rule_type="spec"
            ))

    return violations
