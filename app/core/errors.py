from typing import Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
    details: Optional[Any] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail

class IncubrixAPIException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        status_code: int = 400,
        details: Optional[Any] = None
    ):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.details = details
        super().__init__(message)

# Standard Appendix A & Integration Standard Error Codes
class ErrorCodes:
    DEST_SPEC_VIOLATION = "DEST_SPEC_VIOLATION"
    DEST_RULE_FREQUENCY_CAP = "DEST_RULE_FREQUENCY_CAP"
    CONNECTION_AUTH_EXPIRED = "CONNECTION_AUTH_EXPIRED"
    PLATFORM_RATE_LIMIT = "PLATFORM_RATE_LIMIT"
    PLATFORM_QUOTA_EXHAUSTED = "PLATFORM_QUOTA_EXHAUSTED"
    PLATFORM_CONTENT_REJECTED = "PLATFORM_CONTENT_REJECTED"
    PLATFORM_UNAVAILABLE = "PLATFORM_UNAVAILABLE"
    CONNECTOR_DISABLED = "CONNECTOR_DISABLED"
    
    # Internal & System Errors
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    DESTINATION_NOT_FOUND = "DESTINATION_NOT_FOUND"
    CONNECTOR_NOT_FOUND = "CONNECTOR_NOT_FOUND"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"

def create_error_response(code: str, message: str, retryable: bool, details: Any = None, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details
            }
        }
    )

async def incubrix_exception_handler(request: Request, exc: IncubrixAPIException) -> JSONResponse:
    return create_error_response(
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
        status_code=exc.status_code
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return create_error_response(
        code=ErrorCodes.INTERNAL_SERVER_ERROR,
        message=str(exc) if str(exc) else "An unexpected error occurred.",
        retryable=True,
        status_code=500
    )
