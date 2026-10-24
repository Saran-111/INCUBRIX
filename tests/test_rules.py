import pytest
from app.connectors.base import Rendition, Destination
from app.rules_engine.checker import PostingRulesEngine

@pytest.fixture
def rules_engine():
    return PostingRulesEngine()

def test_frequency_cap_enforcement(rules_engine):
    """
    Must-have 4: Verify second post inside a weekly cap is blocked.
    """
    dest = Destination(
        name="Weekly Digest Community",
        url="https://weekly.test.org",
        platform_key="discourse",
        connector_key="discourse",
        frequency_cap="1/7d"
    )
    rendition = Rendition(
        title="First Post of the Week",
        body="Discussing software distribution patterns and community moderation.",
        tags=["tech"]
    )

    # First post should pass
    res1 = rules_engine.check_rules(rendition, dest)
    assert res1.passed is True
    
    # Record first post
    rules_engine.record_post(dest.url)

    # Second post attempted immediately within 7-day cap window
    res2 = rules_engine.check_rules(rendition, dest)
    assert res2.passed is False
    assert any(v["rule"] == "FREQUENCY_CAP" for v in res2.violations)
    assert res2.reschedule_at is not None

def test_self_promotion_policy_enforcement(rules_engine):
    """
    Must-have 4: Verify promotional post to a no-promotion destination is blocked.
    """
    dest = Destination(
        name="Strict Anti-Promo Forum",
        url="https://strict.test.org",
        platform_key="discourse",
        connector_key="discourse",
        self_promo_allowed=False
    )
    
    # Explicit promo flag
    rendition_promo = Rendition(
        title="Buy our software now!",
        body="Special discount available for readers.",
        is_promotional=True
    )
    res = rules_engine.check_rules(rendition_promo, dest)
    assert res.passed is False
    assert any(v["rule"] == "SELF_PROMOTION_BANNED" for v in res.violations)

    # Text signal trigger
    rendition_text_promo = Rendition(
        title="Check out our pricing",
        body="Sign up today for a free trial and discount code.",
        is_promotional=False
    )
    res2 = rules_engine.check_rules(rendition_text_promo, dest)
    assert res2.passed is False
    assert any(v["rule"] == "SELF_PROMOTION_BANNED" for v in res2.violations)

def test_link_policy_enforcement(rules_engine):
    dest = Destination(
        name="No Link Community",
        url="https://nolink.test.org",
        platform_key="lemmy",
        connector_key="lemmy",
        link_policy="banned"
    )
    rendition = Rendition(
        title="Community Discussion",
        body="Read full details at https://mywebsite.com/full-post"
    )
    res = rules_engine.check_rules(rendition, dest)
    assert res.passed is False
    assert any(v["rule"] == "LINKS_BANNED" for v in res.violations)

def test_ai_disclosure_enforcement(rules_engine):
    dest = Destination(
        name="AI Labelled Forum",
        url="https://ailabel.test.org",
        platform_key="discourse",
        connector_key="discourse",
        disclosure_required=True
    )
    rendition_undisclosed = Rendition(
        title="Machine Learning Synthesis",
        body="A high-level synthesis of modern transformer architectures without notice.",
        ai_generated=True
    )
    res = rules_engine.check_rules(rendition_undisclosed, dest)
    assert res.passed is False
    assert any(v["rule"] == "AI_DISCLOSURE_REQUIRED" for v in res.violations)
