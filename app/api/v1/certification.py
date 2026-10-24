from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.catalogue.importer import catalogue_store
from app.catalogue.models import DestinationRecord
from app.certification.harness import certification_harness, CertificationEvidence
from app.certification.scheduler import recertification_scheduler, RecertificationSummary, RecertificationTicket
from app.core.errors import ErrorCodes, IncubrixAPIException

router = APIRouter(prefix="/api/v1/certification", tags=["Certification"])

class CertifyRequest(BaseModel):
    destination_url: str
    platform_key: str

@router.post("/run", response_model=CertificationEvidence)
async def run_certification_probe(req: CertifyRequest):
    """
    Core & Must-have 2: Full certification run (publish, confirm live, status, delete)
    with stored evidence.
    """
    dest = await catalogue_store.get_by_identity(req.platform_key, req.destination_url)
    if not dest:
        # Fallback create temporary destination record
        dest = DestinationRecord(
            name=f"Probe for {req.platform_key}",
            url=req.destination_url,
            platform_key=req.platform_key,
            connector_key=req.platform_key
        )
    evidence = await certification_harness.certify_destination(dest)
    return evidence

@router.post("/recertify", response_model=RecertificationSummary)
async def trigger_recertification(force_all: bool = Query(False)):
    """
    Outstanding Level: Recertification daemon testing destinations under 30 days.
    """
    return await recertification_scheduler.run_recertification_cycle(force_all=force_all)

@router.get("/tickets", response_model=List[RecertificationTicket])
async def list_recertification_tickets():
    return recertification_scheduler.tickets
