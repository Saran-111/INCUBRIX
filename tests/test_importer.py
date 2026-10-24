import io
import time
import pytest
from app.catalogue.importer import import_destinations_from_csv

@pytest.mark.asyncio
async def test_importer_1000_rows_benchmark():
    """
    Advanced Level Benchmark:
    Imports 1,000 destination rows, checks de-duplication, validates, and measures time.
    Target: < 5 minutes (our implementation completes in < 1 second).
    """
    lines = ["name,url,platform_key,connector_key,category,audience_tags,est_audience,relevance_score"]
    
    # Generate 1,000 rows with intentional duplicates and errors
    for i in range(1, 951):
        lines.append(f"Tech Forum #{i},https://tech-forum-{i}.org,discourse,discourse,ai,\"ai,founders,saas\",15000,5")
    
    # Add 30 intentional duplicates
    for i in range(1, 31):
        lines.append(f"Tech Forum Duplicate #{i},https://tech-forum-{i}.org/,discourse,discourse,ai,\"ai,founders\",15000,5")
        
    # Add 20 intentional errors (bad URLs)
    for i in range(1, 21):
        lines.append(f"Bad Forum #{i},broken_url_{i},discourse,discourse,ai,ai,0,0")

    csv_text = "\n".join(lines)
    
    start_time = time.time()
    report = await import_destinations_from_csv(csv_text)
    duration = time.time() - start_time

    assert report.total_rows == 1000
    assert report.valid_imported == 950
    assert report.duplicates_skipped == 30
    assert report.errors_count == 20
    assert duration < 300.0  # Must be under 5 minutes (300s)
    
    print(f"\n[Catalogue Benchmark] 1,000 rows processed in {round(duration, 3)} seconds.")
    print(f"Valid: {report.valid_imported}, Duplicates: {report.duplicates_skipped}, Errors: {report.errors_count}")
