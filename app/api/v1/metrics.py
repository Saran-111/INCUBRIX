from typing import Optional
from fastapi import APIRouter, Query
from app.connectors.base import Connection, MetricsResult
from app.connectors.registry import connector_registry

router = APIRouter(prefix="/api/v1/metrics", tags=["Metrics"])

@router.get("/{connector_key}/{platform_post_id}", response_model=MetricsResult)
async def get_metrics(
    connector_key: str,
    platform_post_id: str,
    since: Optional[str] = Query(None)
):
    """
    Outstanding Level: Normalised metrics across views, likes, comments, shares, saves, clicks.
    """
    connector = connector_registry.get(connector_key)
    conn = Connection()
    metrics = await connector.fetch_metrics(platform_post_id, conn, since)
    return metrics
