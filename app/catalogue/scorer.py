from typing import List, Tuple

TARGET_PILLARS = {
    "ai": ["ai", "artificial intelligence", "machine learning", "llm", "generative ai", "deep learning", "neural"],
    "video": ["video", "youtube", "cinematography", "video editing", "streaming", "multimedia", "short form video", "animation"],
    "marketing": ["marketing", "growth", "seo", "content marketing", "copywriting", "advertising", "social media", "branding"],
    "saas": ["saas", "software as a service", "b2b", "subscription", "micro-saas", "cloud"],
    "creators": ["creators", "content creation", "podcasting", "blogging", "writing", "newsletter", "influencer"],
    "founders": ["founders", "startups", "entrepreneurship", "indie hacker", "bootstrapping", "venture", "business building"]
}

def calculate_relevance_score(
    name: str,
    category: str,
    audience_tags: List[str],
    description: str = ""
) -> Tuple[int, str]:
    """
    Scores a destination from 1 to 5 based on match with IncuBrix target audiences:
    AI, video, marketing, SaaS, creators, and founders.
    """
    matched_pillars = set()
    combined_text = f"{name} {category} {' '.join(audience_tags)} {description}".lower()

    for pillar, keywords in TARGET_PILLARS.items():
        if any(kw in combined_text for kw in keywords):
            matched_pillars.add(pillar)

    pillar_count = len(matched_pillars)

    if pillar_count >= 3:
        score = 5
        reason = f"High-value match across core IncuBrix pillars: {', '.join(sorted(matched_pillars))}."
    elif pillar_count == 2:
        score = 4
        reason = f"Strong alignment with target audiences: {', '.join(sorted(matched_pillars))}."
    elif pillar_count == 1:
        score = 3
        reason = f"Direct alignment with {list(matched_pillars)[0]} audience."
    else:
        # Check if broad technology or business
        broad_keywords = ["technology", "programming", "software", "developer", "design", "business", "community"]
        if any(kw in combined_text for kw in broad_keywords):
            score = 2
            reason = "Adjacent tech or business community with partial creator/founder overlap."
        else:
            score = 1
            reason = "Unrelated niche outside of AI, video, marketing, SaaS, creator, or founder focus."

    return score, reason
