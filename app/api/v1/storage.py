from fastapi import APIRouter, File, UploadFile, Response
from fastapi.responses import Response as FastApiResponse
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.storage.s3_adapter import storage_service

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Uploads file to S3/local storage and returns download link."""
    content = await file.read()
    download_url = await storage_service.save_file(content, file.filename, file.content_type or "application/octet-stream")
    return {"filename": file.filename, "download_url": download_url}

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Downloads stored file/artifact."""
    data = await storage_service.get_file(filename)
    if data is None:
        raise IncubrixAPIException(
            code=ErrorCodes.INVALID_PAYLOAD,
            message=f"File '{filename}' not found.",
            status_code=404
        )
    return FastApiResponse(content=data, media_type="application/octet-stream")
