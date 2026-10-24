# SOURCES.md — Commercial Licensing & Sources Disclosure

All software, libraries, APIs, and datasets used in the IncuBrix Long-Tail Destination Network adhere to permissive commercial open-source licenses (MIT, Apache 2.0, BSD-3-Clause). No copyleft (AGPL/GPL) or non-commercial (CC BY-NC) components exist in the default execution path.

---

## 1. Core Python Dependencies & Libraries

| Library | Version | License | Commercial Use Permitted? | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **FastAPI** | `>=0.115.0` | MIT | Yes | High-performance asynchronous API framework and OpenAPI 3.1 generation |
| **Uvicorn** | `>=0.32.0` | BSD-3-Clause | Yes | Lightning-fast ASGI web server implementation |
| **Pydantic** | `>=2.10.0` | MIT | Yes | Data validation, contract schema definitions, and settings management |
| **Pydantic-Settings** | `>=2.6.0` | MIT | Yes | Environment variable configuration loader |
| **HTTPX** | `>=0.28.0` | BSD-3-Clause | Yes | Next-generation asynchronous HTTP client for connector dispatch |
| **PyYAML** | `>=6.0.2` | MIT | Yes | Parsing Appendix A connector YAML manifests |
| **Aiofiles** | `>=24.1.0` | Apache-2.0 | Yes | Asynchronous non-blocking disk I/O operations |
| **Boto3** | `>=1.35.0` | Apache-2.0 | Yes | Amazon S3 and MinIO storage client |
| **Pytest** | `>=8.3.0` | MIT | Yes | Unit, integration, and contract test runner |
| **Pytest-Asyncio** | `>=0.24.0` | Apache-2.0 | Yes | Asynchronous test fixture orchestration |
| **OpenPyXL** | `>=3.1.5` | MIT | Yes | Excel submission form automation |

---

## 2. Infrastructure & Container Images

| Image | Base / Source | License | Purpose |
| :--- | :--- | :--- | :--- |
| **python:3.11-slim** | Debian GNU/Linux | Free / Open Source | Base container runtime |
| **MinIO (minio/minio)** | MinIO Inc. | AGPLv3 (Isolated sidecar container, no linked code) | Local S3-compatible object storage container |
| **Ghost (ghost:5-alpine)** | Ghost Foundation | MIT | Local target blog instance for end-to-end publish verification |

---

## 3. Data & Researched Catalogue Sources

| Dataset / File | Source / Origin | License | Purpose |
| :--- | :--- | :--- | :--- |
| `data/real_catalogue_150.csv` | Researched by candidate from public community guidelines | Public Domain / CC0 | Catalogue of 165 long-tail destinations |
| `data/labelled_benchmark.json` | Candidate annotated dataset | Proprietary / CC0 | Gold-standard test cases for measuring Recommender Precision@10 |
| `data/test_inputs/*` | Candidate synthesized test payloads | CC0 | Batch runner test packs |
