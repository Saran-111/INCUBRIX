from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel
from app.connectors.base import (
    Rendition, Destination, Connection,
    ValidationResult, PublishResult, StatusResult, DeleteResult,
    MetricsResult, AssistPackResult, RefreshAuthResult
)
from app.connectors.registry import connector_registry
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.core.idempotency import idempotency_store

router = APIRouter(prefix="", tags=["Connectors"])

class ConnectorMethodPayload(BaseModel):
    rendition: Optional[Rendition] = None
    destination: Optional[Destination] = None
    connection: Optional[Connection] = None
    platform_post_id: Optional[str] = None
    since: Optional[str] = None
    idempotency_key: Optional[str] = None

@router.get("/connector/v1/manifests")
async def list_manifests():
    return {"manifests": connector_registry.list_all()}

@router.get("/connector/v1/manifests/{connector_key}")
async def get_manifest(connector_key: str):
    return connector_registry.get_manifest(connector_key)

@router.post("/connector/v1/{connector_key}/{method}")
async def invoke_connector_method(
    connector_key: str,
    method: str,
    payload: ConnectorMethodPayload,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Appendix A Connector Contract invocation endpoint:
    POST /connector/v1/{connector_key}/{method}
    """
    connector = connector_registry.get(connector_key)
    conn = payload.connection or Connection()

    if method == "validate":
        if not payload.rendition:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'rendition' in validate request")
        dest = payload.destination or Destination(
            name="Generic Destination",
            url="https://example.com",
            platform_key=connector_key,
            connector_key=connector_key
        )
        res = await connector.validate(payload.rendition, dest, conn)
        return res.model_dump()

    elif method == "publish":
        if not payload.rendition:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'rendition' in publish request")
        
        dest = payload.destination or Destination(
            name="Generic Destination",
            url="https://example.com",
            platform_key=connector_key,
            connector_key=connector_key
        )
        
        from app.core.idempotency import compute_request_hash
        req_hash = compute_request_hash(payload.rendition, dest, connector_key)
        idem_key = idempotency_key_header or payload.idempotency_key or f"publish_{connector_key}_{req_hash[:16]}"
        
        # Check idempotency
        record, is_new = await idempotency_store.get_or_create(idem_key, req_hash)
        if not is_new:
            if record.request_hash and record.request_hash != req_hash:
                raise IncubrixAPIException(
                    code=ErrorCodes.IDEMPOTENCY_CONFLICT,
                    message="Idempotency-Key already used with a different request payload.",
                    status_code=409,
                    retryable=False
                )
            if record.status == "IN_PROGRESS":
                try:
                    await asyncio.wait_for(record.event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    raise IncubrixAPIException(
                        code=ErrorCodes.IDEMPOTENCY_CONFLICT,
                        message="Concurrent request with this Idempotency-Key is currently in progress.",
                        status_code=409,
                        retryable=True
                    )
            if record.status == "COMPLETED" and record.response_data:
                return record.response_data
            if record.status == "FAILED" and record.response_data:
                raise IncubrixAPIException(
                    code=record.response_data.get("code", ErrorCodes.INTERNAL_SERVER_ERROR),
                    message=record.response_data.get("message", "Previous idempotent request failed."),
                    status_code=record.response_status_code
                )

        try:
            res = await connector.publish(payload.rendition, dest, conn, idem_key)
            data = res.model_dump()
            await idempotency_store.complete(idem_key, data)
            return data
        except Exception as e:
            if isinstance(e, IncubrixAPIException):
                await idempotency_store.fail(idem_key, {"code": e.code, "message": e.message}, e.status_code)
                raise
            await idempotency_store.fail(idem_key, {"code": ErrorCodes.PLATFORM_UNAVAILABLE, "message": str(e)}, 500)
            raise

    elif method == "get_status":
        if not payload.platform_post_id:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'platform_post_id'")
        res = await connector.get_status(payload.platform_post_id, conn)
        return res.model_dump()

    elif method == "delete":
        if not payload.platform_post_id:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'platform_post_id'")
        res = await connector.delete(payload.platform_post_id, conn)
        return res.model_dump()

    elif method == "fetch_metrics":
        if not payload.platform_post_id:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'platform_post_id'")
        res = await connector.fetch_metrics(payload.platform_post_id, conn, payload.since)
        return res.model_dump()

    elif method == "refresh_auth":
        res = await connector.refresh_auth(conn)
        return res.model_dump()

    elif method == "build_assist_pack":
        if not payload.rendition:
            raise IncubrixAPIException(code=ErrorCodes.INVALID_PAYLOAD, message="Missing 'rendition'")
        dest = payload.destination or Destination(
            name="Assisted Target",
            url="https://example.com",
            platform_key="assisted",
            connector_key="assisted"
        )
        res = await connector.build_assist_pack(payload.rendition, dest)
        return res.model_dump()

    else:
        raise IncubrixAPIException(
            code=ErrorCodes.INVALID_PAYLOAD,
            message=f"Unsupported connector contract method '{method}'",
            status_code=400
        )
