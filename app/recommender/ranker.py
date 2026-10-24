import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.catalogue.models import DestinationRecord
from app.connectors.base import Rendition

class RankedDestination(BaseModel):
    rank: int
    name: str
    url: str
    connector_key: str
    fit_score: float  # 0.0 to 1.0
    fit_reason: str
    rules_passed: bool
    relevance_score: int

class DestinationRecommender:
    def rank_destinations(
        self,
        content: Rendition,
        destinations: List[DestinationRecord],
        top_k: int = 10
    ) -> List[RankedDestination]:
        scored_items = []
        content_category = (content.metadata.get("category") or "").lower()
        content_tokens = set(re.findall(r'\b[a-z]{3,}\b', f"{content.title or ''} {content.body} {' '.join(content.tags)}".lower()))

        for dest in destinations:
            score = 0.0
            reasons = []

            # 1. Past Certification Level & Results (Weight: 25%)
            # High certified levels have verified reliability
            if dest.level == "L4":
                score += 25.0
                reasons.append("L4 certified with verified API delivery & engagement metrics")
            elif dest.level == "L3":
                score += 20.0
                reasons.append("L3 native API certified with verified delivery")
            elif dest.level in ("L1", "L2"):
                score += 12.0
            else:
                score += 2.0  # L0 uncertified

            # 2. Category Alignment (Weight: 25%)
            if content_category and dest.category.lower() == content_category:
                score += 25.0
                reasons.append(f"Category matches target '{dest.category}'")
            elif any(t in dest.category.lower() for t in content.tags):
                score += 15.0

            # 3. Audience Tag Match & Semantic Overlap (Weight: 25%)
            dest_tag_tokens = set(t.lower() for t in dest.audience_tags)
            matched_tags = dest_tag_tokens.intersection(content_tokens)
            if matched_tags:
                tag_weight = min(25.0, len(matched_tags) * 8.0)
                score += tag_weight
                reasons.append(f"Matching audience tags: {', '.join(sorted(matched_tags))}")

            # 4. Audience Scale (Weight: 15%)
            if dest.est_audience >= 200000:
                score += 15.0
                reasons.append(f"High-impact reach ({dest.est_audience:,} audience)")
            elif dest.est_audience >= 50000:
                score += 10.0
            elif dest.est_audience >= 10000:
                score += 5.0

            # 5. Base Catalogue Relevance (Weight: 10%)
            score += (dest.relevance_score / 5.0) * 10.0

            # 6. Rules Compatibility
            rule_compliant = True
            if content.is_promotional and not dest.self_promo_allowed:
                score -= 50.0
                rule_compliant = False
                reasons.append("Penalized: Content is promotional but community bans self-promotion")

            has_links = bool(re.search(r'https?://', content.body))
            if has_links and dest.link_policy == "banned":
                score -= 35.0
                rule_compliant = False
                reasons.append("Penalized: Contains external links prohibited by community")

            if rule_compliant:
                score += 10.0

            final_score = max(0.0, min(100.0, score)) / 100.0
            primary_reason = "; ".join(reasons) if reasons else dest.relevance_reason

            scored_items.append({
                "name": dest.name,
                "url": dest.url,
                "connector_key": dest.connector_key,
                "fit_score": round(final_score, 3),
                "fit_reason": primary_reason,
                "rules_passed": rule_compliant,
                "relevance_score": dest.relevance_score,
                "_raw_score": score
            })

        # Sort descending by raw score
        scored_items.sort(key=lambda x: x["_raw_score"], reverse=True)

        results = []
        for idx, item in enumerate(scored_items[:top_k], start=1):
            results.append(RankedDestination(
                rank=idx,
                name=item["name"],
                url=item["url"],
                connector_key=item["connector_key"],
                fit_score=item["fit_score"],
                fit_reason=item["fit_reason"],
                rules_passed=item["rules_passed"],
                relevance_score=item["relevance_score"]
            ))

        return results

recommender = DestinationRecommender()
