import asyncio
import os
from pathlib import Path
from typing import Optional
import httpx
from app.core.config import settings
from app.core.logging import logger

class StorageService:
    def __init__(self):
        self.local_dir = Path(settings.LOCAL_STORAGE_DIR)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.s3_client = None
        self._init_s3()

    def _init_s3(self):
        if settings.STORAGE_TYPE == "s3" and settings.S3_ENDPOINT_URL:
            try:
                import boto3
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                    region_name=settings.S3_REGION
                )
                # Ensure bucket exists
                try:
                    self.s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
                except Exception:
                    self.s3_client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
            except Exception as e:
                logger.warning(f"Could not connect to S3/MinIO ({str(e)}), defaulting to local storage.")
                self.s3_client = None

    async def save_file(self, content: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        """Saves file to S3 or local storage and returns accessible download link."""
        # Save locally as backup / primary
        local_path = self.local_dir / filename
        local_path.write_bytes(content)

        if self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=filename,
                    Body=content,
                    ContentType=content_type
                )
            except Exception as e:
                logger.warning(f"Failed writing to S3 bucket: {str(e)}")

        return f"/api/v1/storage/download/{filename}"

    async def get_file(self, filename: str) -> Optional[bytes]:
        local_path = self.local_dir / filename
        if local_path.exists():
            return local_path.read_bytes()
        
        if self.s3_client:
            try:
                resp = self.s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=filename)
                return resp["Body"].read()
            except Exception:
                return None
        return None

    async def fetch_input(self, input_val: str) -> bytes:
        """Accepts an upload path, local filename, or remote HTTP URL."""
        input_str = input_val.strip()
        if input_str.startswith("http://") or input_str.startswith("https://"):
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(input_str)
                res.raise_for_status()
                return res.content
        else:
            path = Path(input_str)
            if path.exists():
                return path.read_bytes()
            # Check local storage dir
            local_stored = self.local_dir / input_str
            if local_stored.exists():
                return local_stored.read_bytes()
            raise FileNotFoundError(f"Input file not found: {input_val}")

storage_service = StorageService()
