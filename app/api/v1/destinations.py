from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Query, Body
from pydantic import BaseModel
from app.catalogue.models import DestinationRecord
from app.catalogue.importer import catalogue_store, import_destinations_from_csv, ImportReport
from app.core.errors import ErrorCodes, IncubrixAPIException

router = APIRouter(prefix="/api/v1/destinations", tags=["Destinations"])

class CSVImportTextRequest(BaseModel):
    csv_content: str

@router.get("", response_model=List[DestinationRecord])
async def list_destinations(
    platform: Optional[str] = Query(None),
    connector: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    level: Optional[str] = Query(None)
):
    all_dests = await catalogue_store.list_all()
    filtered = all_dests
    if platform:
        filtered = [d for d in filtered if d.platform_key.lower() == platform.lower()]
    if connector:
        filtered = [d for d in filtered if d.connector_key.lower() == connector.lower()]
    if min_score:
        filtered = [d for d in filtered if d.relevance_score >= min_score]
    if level:
        filtered = [d for d in filtered if d.level.upper() == level.upper()]
    return filtered

@router.post("", response_model=DestinationRecord)
async def add_destination(dest: DestinationRecord):
    """
    Must-have 3: Configuration, not code. Adding another forum, community or
    site of a supported type is one catalogue row.
    """
    await catalogue_store.add_or_update(dest)
    return dest

@router.post("/import/text")
async def import_csv_text(req: CSVImportTextRequest):
    """Imports destinations via raw CSV text."""
    report = await import_destinations_from_csv(req.csv_content)
    return report.to_dict()

@router.post("/import/file")
async def import_csv_file(file: UploadFile = File(...)):
    """Imports destinations via uploaded CSV file."""
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    report = await import_destinations_from_csv(text)
    return report.to_dict()
