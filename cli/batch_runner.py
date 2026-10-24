import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import httpx

async def process_test_item(
    item: Dict[str, Any],
    api_url: str,
    output_dir: Path,
    item_id: str
) -> Dict[str, Any]:
    start_time = time.time()
    url = f"{api_url.rstrip('/')}/api/v1/jobs/publish"
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": item.get("idempotency_key") or f"batch_{item_id}_{int(time.time()*1000)}"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=item, headers=headers)
            if resp.status_code not in (200, 202):
                result_data = {
                    "item_id": item_id,
                    "status": "failed",
                    "status_code": resp.status_code,
                    "error": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                    "duration_s": round(time.time() - start_time, 3)
                }
            else:
                job_data = resp.json()
                job_id = job_data.get("job_id")
                
                # Poll for completion if async
                final_job = job_data
                for _ in range(60):  # Wait up to 30s
                    if final_job.get("status") in ("succeeded", "failed"):
                        break
                    await asyncio.sleep(0.5)
                    poll_resp = await client.get(f"{api_url.rstrip('/')}/api/v1/jobs/{job_id}")
                    if poll_resp.status_code == 200:
                        final_job = poll_resp.json()

                result_data = {
                    "item_id": item_id,
                    "status": final_job.get("status"),
                    "job_id": job_id,
                    "result": final_job.get("result"),
                    "manifest": final_job.get("manifest"),
                    "error": final_job.get("error"),
                    "duration_s": round(time.time() - start_time, 3)
                }

    except Exception as e:
        result_data = {
            "item_id": item_id,
            "status": "exception",
            "error": str(e),
            "duration_s": round(time.time() - start_time, 3)
        }

    out_file = output_dir / f"result_{item_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    return result_data

async def run_batch(input_path_str: str, output_path_str: str, api_url: str):
    input_path = Path(input_path_str)
    output_dir = Path(output_path_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    items: List[tuple[str, Dict[str, Any]]] = []

    if input_path.is_file():
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                for idx, obj in enumerate(data):
                    items.append((f"{input_path.stem}_{idx+1}", obj))
            elif isinstance(data, dict):
                items.append((input_path.stem, data))
    elif input_path.is_dir():
        for file in sorted(input_path.glob("*.json")):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for idx, obj in enumerate(data):
                        items.append((f"{file.stem}_{idx+1}", obj))
                else:
                    items.append((file.stem, data))

    print(f"[Batch Runner] Loaded {len(items)} test inputs. Executing against {api_url}...")
    start_batch = time.time()
    
    tasks = [
        process_test_item(item, api_url, output_dir, item_id)
        for item_id, item in items
    ]
    results = await asyncio.gather(*tasks)

    succeeded = sum(1 for r in results if r.get("status") == "succeeded")
    failed = sum(1 for r in results if r.get("status") in ("failed", "exception"))

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_inputs": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "total_duration_s": round(time.time() - start_batch, 3),
        "api_url": api_url,
        "results": results
    }

    summary_file = output_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[Batch Runner] Finished in {summary['total_duration_s']}s. Succeeded: {succeeded}, Failed: {failed}")
    print(f"[Batch Runner] Full results written to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="IncuBrix Batch Runner CLI (Integration Standard 10)")
    parser.add_argument("--input", "-i", required=True, help="Path to input JSON file or folder of test files")
    parser.add_argument("--output", "-o", required=True, help="Directory to write all output results to")
    parser.add_argument("--api-url", "-u", default="http://localhost:8000", help="Base URL of running IncuBrix service")
    
    args = parser.parse_args()
    asyncio.run(run_batch(args.input, args.output, args.api_url))

if __name__ == "__main__":
    main()
