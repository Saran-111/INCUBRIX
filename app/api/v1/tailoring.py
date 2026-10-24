from fastapi import APIRouter
from pydantic import BaseModel
from app.connectors.base import Rendition, Destination
from app.tailoring.engine import tailoring_engine

router = APIRouter(prefix="/api/v1/tailor", tags=["Tailoring"])

class TailorRequest(BaseModel):
    rendition: Rendition
    destination: Destination

@router.post("", response_model=Rendition)
async def tailor_content(req: TailorRequest):
    """
    Advanced Level: Adapts title and text (discussion framing, canonical URL,
    word boundary truncation, hashtags, AI disclosure).
    """
    return tailoring_engine.tailor_rendition(req.rendition, req.destination)
