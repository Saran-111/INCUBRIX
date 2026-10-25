import asyncio
import time
import uuid
from typing import Any, Dict, Optional
from fastapi import HTTPException
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException

class MockPlatformState:
    """Stores posts created in simulation mode for lifecycle testing (status, metrics, deletion)."""
    def __init__(self):
        self.posts: Dict[str, Dict[str, Any]] = {}
        # Injected failure triggers for testing hard cases
        self.trigger_429: bool = False
        self.retry_after_seconds: int = 2
        self.trigger_expired_token: bool = False
        self.trigger_content_rejection: bool = False
        self.trigger_renamed_field: bool = False
        self.trigger_timeout: bool = False
        self.publish_delay_s: float = 0.0
        self.publish_call_count: int = 0

    def reset_triggers(self):
        self.trigger_429 = False
        self.retry_after_seconds = 2
        self.trigger_expired_token = False
        self.trigger_content_rejection = False
        self.trigger_renamed_field = False
        self.trigger_timeout = False
        self.publish_delay_s = 0.0
        self.publish_call_count = 0

mock_state = MockPlatformState()

async def simulate_network_call(connector_key: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates remote platform HTTP calls with realistic behavior and injected test triggers.
    """
    if action == "publish":
        mock_state.publish_call_count += 1
        if mock_state.publish_delay_s > 0:
            await asyncio.sleep(mock_state.publish_delay_s)

    if settings.MOCK_LATENCY_MS > 0:
        await asyncio.sleep(settings.MOCK_LATENCY_MS / 1000.0)

    # Check for hard-case failure injections
    if mock_state.trigger_timeout:
        # Simulate timeout
        await asyncio.sleep(0.5)
        raise IncubrixAPIException(
            code=ErrorCodes.PLATFORM_UNAVAILABLE,
            message="Platform connection timed out after 5000ms",
            retryable=True,
            status_code=504
        )

    if mock_state.trigger_429:
        raise IncubrixAPIException(
            code=ErrorCodes.PLATFORM_RATE_LIMIT,
            message=f"Rate limit exceeded. Try again in {mock_state.retry_after_seconds}s",
            retryable=True,
            status_code=429,
            details={"retry_after": mock_state.retry_after_seconds}
        )

    if mock_state.trigger_expired_token:
        raise IncubrixAPIException(
            code=ErrorCodes.CONNECTION_AUTH_EXPIRED,
            message="The provided access token or API key is expired or has been revoked.",
            retryable=False,
            status_code=401
        )

    if mock_state.trigger_content_rejection:
        raise IncubrixAPIException(
            code=ErrorCodes.PLATFORM_CONTENT_REJECTED,
            message="Content violated community moderation policy or banned keyword detected.",
            retryable=False,
            status_code=422,
            details={"moderation_flag": "flagged_by_automod"}
        )

    # If action is publish
    if action == "publish":
        post_id = f"{connector_key}_{uuid.uuid4().hex[:10]}"
        live_url = f"https://mock.{connector_key}.org/p/{post_id}"
        
        # Hard case: platform renames a field in its API response
        if mock_state.trigger_renamed_field:
            return {
                "post_identifier_legacy": post_id,
                "url_string": live_url,
                "post_status": "published"
            }

        post_record = {
            "post_id": post_id,
            "connector_key": connector_key,
            "live_url": live_url,
            "status": "live",
            "created_at": time.time(),
            "payload": payload,
            "metrics": {
                "views": 142,
                "likes": 28,
                "comments": 6,
                "shares": 3,
                "saves": 4,
                "watch_time_s": 0,
                "clicks": 19
            }
        }
        mock_state.posts[post_id] = post_record
        return {
            "platform_post_id": post_id,
            "live_url": live_url,
            "status": "published"
        }

    elif action == "get_status":
        post_id = payload.get("platform_post_id")
        if post_id in mock_state.posts:
            item = mock_state.posts[post_id]
            return {
                "status": item["status"],
                "live_url": item["live_url"]
            }
        return {"status": "not_found", "live_url": None}

    elif action == "delete":
        post_id = payload.get("platform_post_id")
        if post_id in mock_state.posts:
            mock_state.posts[post_id]["status"] = "deleted"
            return {"deleted": True}
        return {"deleted": False}

    elif action == "fetch_metrics":
        post_id = payload.get("platform_post_id")
        if post_id in mock_state.posts:
            return mock_state.posts[post_id]["metrics"]
        return {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "watch_time_s": 0,
            "clicks": 0
        }

    return {}
