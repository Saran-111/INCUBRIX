import re
from typing import List, Optional
from app.connectors.base import Rendition, Destination

def truncate_at_word_boundary(text: str, max_chars: int, suffix: str = "...") -> str:
    """Truncates text at the nearest word boundary without splitting words."""
    if not text or len(text) <= max_chars:
        return text
    
    target_len = max_chars - len(suffix)
    if target_len <= 0:
        return text[:max_chars]
        
    truncated = text[:target_len]
    last_space = truncated.rfind(' ')
    if last_space != -1 and last_space > target_len // 2:
        truncated = truncated[:last_space]
        
    return truncated.rstrip() + suffix

class ContentTailoringEngine:
    def tailor_rendition(self, rendition: Rendition, destination: Destination) -> Rendition:
        title = rendition.title or ""
        body = rendition.body
        media = list(rendition.media_urls)
        tags = list(rendition.tags)
        canonical_url = rendition.canonical_url

        connector = destination.connector_key.lower()

        # 1. Discussion-first framing for forums & discussion platforms
        if connector in ("discourse", "lemmy", "slack"):
            if title and not title.endswith("?"):
                # Frame title as an engaging discussion
                if not any(title.lower().startswith(q) for q in ["how", "what", "why", "is", "can", "are", "do"]):
                    title = f"Discussion: {title}"
            
            # Ensure conversational closing prompt in body
            if not body.strip().endswith("?"):
                body = f"{body}\n\nWhat are your thoughts or experiences with this?"

        # 2. Canonical URL for developer articles & blogs
        elif connector in ("devto", "ghost", "hashnode"):
            if not canonical_url and rendition.metadata.get("source_url"):
                canonical_url = rendition.metadata["source_url"]

        # 3. Format hashtags and tags according to platform specs
        if connector in ("devto", "hashnode"):
            # Max 4 lowercase alphanumeric tags, no spaces
            clean_tags = [re.sub(r'[^a-zA-Z0-9]', '', t.lower()) for t in tags]
            tags = [t for t in clean_tags if t][:4]
        elif connector == "discourse":
            # Alphanumeric with hyphens, max 5
            tags = [re.sub(r'[^a-zA-Z0-9\-]', '', t.lower()) for t in tags][:5]

        # 4. Enforce word-boundary truncation based on known limits
        if connector == "discourse":
            title = truncate_at_word_boundary(title, 255)
            body = truncate_at_word_boundary(body, 32000)
        elif connector == "lemmy":
            title = truncate_at_word_boundary(title, 200)
            body = truncate_at_word_boundary(body, 10000)
        elif connector == "devto":
            title = truncate_at_word_boundary(title, 128)
            body = truncate_at_word_boundary(body, 50000)
        elif connector == "ghost":
            title = truncate_at_word_boundary(title, 255)
        elif connector == "mailchimp":
            title = truncate_at_word_boundary(title, 150)

        # 5. Mandatory AI disclosure insertion if required by destination
        if destination.disclosure_required and rendition.ai_generated:
            disclosure_notice = "\n\n*(Disclosure: This post was prepared with the assistance of AI tools and verified for accuracy by the author.)*"
            if "disclosure:" not in body.lower() and "ai generated" not in body.lower():
                body = body + disclosure_notice

        return Rendition(
            title=title,
            body=body,
            media_urls=media,
            tags=tags,
            canonical_url=canonical_url,
            is_promotional=rendition.is_promotional,
            ai_generated=rendition.ai_generated,
            metadata=rendition.metadata
        )

tailoring_engine = ContentTailoringEngine()
