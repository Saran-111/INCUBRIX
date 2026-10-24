import pytest
from app.catalogue.importer import catalogue_store, import_destinations_from_csv
from app.recommender.benchmark import evaluate_recommender_precision
from pathlib import Path

@pytest.mark.asyncio
async def test_recommender_top_10_precision_benchmark():
    """
    Outstanding Level:
    Measures Top-10 precision across the labelled gold-standard dataset.
    """
    # Load 150+ catalogue
    cat_path = Path("data/real_catalogue_150.csv")
    if cat_path.exists():
        csv_text = cat_path.read_text(encoding="utf-8")
        await import_destinations_from_csv(csv_text)

    destinations = await catalogue_store.list_all()
    assert len(destinations) >= 150, f"Expected at least 150 destinations, got {len(destinations)}"

    benchmark_res = evaluate_recommender_precision(destinations)
    
    print(f"\n[Recommender Benchmark] Mean Precision@10: {benchmark_res.mean_precision_at_10:.4f} ({benchmark_res.to_dict()['percentage']})")
    for item in benchmark_res.item_results:
        print(f"  - '{item['title'][:40]}...': Hits={item['top_10_hits']}/10, P@10={item['precision_at_10']}")

    # Precision should exceed 70% (0.70)
    assert benchmark_res.mean_precision_at_10 >= 0.70
