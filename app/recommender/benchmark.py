import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.catalogue.models import DestinationRecord
from app.connectors.base import Rendition
from app.recommender.ranker import recommender

class BenchmarkResult:
    def __init__(self):
        self.item_results: List[Dict[str, Any]] = []
        self.mean_precision_at_10: float = 0.0

    def to_dict(self):
        return {
            "total_items_evaluated": len(self.item_results),
            "mean_precision_at_10": round(self.mean_precision_at_10, 4),
            "percentage": f"{round(self.mean_precision_at_10 * 100, 2)}%",
            "item_results": self.item_results
        }

def evaluate_recommender_precision(
    destinations: List[DestinationRecord],
    benchmark_file_path: Optional[str] = None
) -> BenchmarkResult:
    if not benchmark_file_path:
        benchmark_file_path = str(Path(__file__).parent.parent.parent / "data" / "labelled_benchmark.json")

    with open(benchmark_file_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    result = BenchmarkResult()
    total_precision = 0.0

    def clean_url(u: str) -> str:
        u = u.lower().strip().rstrip('/')
        return u.replace("https://www.", "https://").replace("http://www.", "http://")

    for item in benchmark_data:
        content = Rendition(
            title=item.get("title", ""),
            body=item.get("body", ""),
            tags=item.get("tags", []),
            is_promotional=item.get("is_promotional", False),
            ai_generated=item.get("ai_generated", False),
            metadata={"category": item.get("category")}
        )
        ground_truth_urls = set(clean_url(u) for u in item.get("relevant_destinations", []))

        ranked = recommender.rank_destinations(content, destinations, top_k=10)
        top_10_urls = [clean_url(r.url) for r in ranked]

        # Calculate matches
        hits = sum(1 for url in top_10_urls if url in ground_truth_urls)
        p_at_10 = hits / 10.0
        total_precision += p_at_10

        result.item_results.append({
            "title": content.title,
            "category": item.get("category"),
            "ground_truth_count": len(ground_truth_urls),
            "top_10_hits": hits,
            "precision_at_10": p_at_10
        })

    if benchmark_data:
        result.mean_precision_at_10 = total_precision / len(benchmark_data)

    return result
