"""
scripts/export_api_docs.py
----------------------------
Day 40 - export docs/openapi.json (straight from the FastAPI app's
own schema) and a docs/postman_collection.json derived from it, so
the API can be explored/imported without running the server.

Run with:
    PYTHONPATH=. python3 scripts/export_api_docs.py
"""

import json
from pathlib import Path

from src.api.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
BASE_URL = "http://localhost:8000"


def export_openapi():
    spec = app.openapi()
    out_path = DOCS_DIR / "openapi.json"
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
    return spec, out_path


def _example_params(param_schema):
    """A reasonable example value for a query param, used to pre-fill
    the Postman request so it's runnable out of the box."""
    name = param_schema.get("name", "")
    ptype = param_schema.get("schema", {}).get("type", "string")

    examples = {
        "ticker": "TCS",
        "company_id": "TCS",
        "preset": "Quality",
        "sector": "Information Technology",
        "broad_sector": "Information Technology",
        "peer_group_name": "IT Services",
        "group_name": "IT Services",
        "min_roe": "15",
        "max_de": "1.5",
        "min_fcf": "0",
        "min_rev_cagr_5yr": "10",
        "min_pat_cagr_5yr": "10",
        "max_pe": "40",
        "search": "Tata",
        "year": "2023",
        "from_year": "2020",
        "to_year": "2023",
    }
    if name in examples:
        return examples[name]
    return "1" if ptype in ("integer", "number") else "example"


def build_postman_collection(spec):
    items = []

    for path, methods in spec["paths"].items():
        for method, details in methods.items():
            if method.lower() != "get":
                continue

            # Fill path params with example values so requests are
            # runnable straight out of the collection.
            resolved_path = path
            query_params = []

            for param in details.get("parameters", []):
                value = str(_example_params(param))
                if param.get("in") == "path":
                    resolved_path = resolved_path.replace(f"{{{param['name']}}}", value)
                elif param.get("in") == "query":
                    required = param.get("required", False)
                    query_params.append({
                        "key": param["name"],
                        "value": value,
                        "disabled": not required,
                    })

            url_path_segments = [seg for seg in resolved_path.split("/") if seg]

            items.append({
                "name": details.get("summary") or details.get("operationId") or path,
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": BASE_URL + resolved_path,
                        "host": ["{{base_url}}"],
                        "path": url_path_segments,
                        "query": query_params,
                    },
                    "description": details.get("description", ""),
                },
                "response": [],
            })

    collection = {
        "info": {
            "name": "Nifty100 Data Foundation API",
            "description": "Auto-generated from the FastAPI OpenAPI schema.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": BASE_URL, "type": "string"},
        ],
        "item": items,
    }
    return collection


def export_postman(spec):
    collection = build_postman_collection(spec)
    out_path = DOCS_DIR / "postman_collection.json"
    with open(out_path, "w") as f:
        json.dump(collection, f, indent=2)
    return out_path


if __name__ == "__main__":
    DOCS_DIR.mkdir(exist_ok=True)
    spec, openapi_path = export_openapi()
    postman_path = export_postman(spec)
    print(f"Wrote {openapi_path} ({len(spec['paths'])} paths)")
    print(f"Wrote {postman_path}")
