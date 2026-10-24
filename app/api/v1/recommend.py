from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.catalogue.importer import catalogue_store
from app.connectors.base import Rendition
from app.recommender.ranker import recommender, RankedDestination
from app.recommender.benchmark import evaluate_recommender_precision

router = APIRouter(prefix="/api/v1/recommend", tags=["Recommender"])

class RecommendationRequest(BaseModel):
    rendition: Rendition
    top_k: int = 10

@router.post("", response_model=List[RankedDestination])
async def recommend_destinations(req: RecommendationRequest):
    """
    Outstanding Level: Recommender ranks destinations by fit (audience, rules, past results)
    with a clear reason for each.
    """
    all_destinations = await catalogue_store.list_all()
    ranked = recommender.rank_destinations(
        content=req.rendition,
        destinations=all_destinations,
        top_k=req.top_k
    )
    return ranked

@router.get("/benchmark")
async def run_benchmark():
    """
    Outstanding Level: Measures precision of the top 10 on labelled benchmark set.
    """
    all_destinations = await catalogue_store.list_all()
    results = evaluate_recommender_precision(all_destinations)
    return results.to_dict()
