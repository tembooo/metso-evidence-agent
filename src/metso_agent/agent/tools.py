"""Safe, narrow adapters to the existing Stage 03 and Stage 05 tools.

Importing this module makes no network calls, and never publishes raw files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from metso_agent.retrieval.brochure_loader import load_brochures
from metso_agent.analytics.flotation import analyze_csv  # STAGE08_FLOTATION
from metso_agent.retrieval.product_search import ProductSearcher
from metso_agent.estimation.cost_estimator import (
    ServiceRequest,
    build_planning_comparison,
    load_ledger,
)

# Responses API function tools: strict schema => all properties required,
# nullable or enumerated when information is not yet available.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_product_brochures",
        "description": "Search ONLY the supplied Metso product brochures for technical evidence. Use for product features, suitability and recommendations; never for prices.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Customer product question or technical need"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "compare_service_costs",
        "description": "Compare historical service evidence for a specific job; do NOT issue a commercial quote. If equipment, country, task, or quantity is missing, ask the user instead of guessing.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "equipment": {"type": "string"},
                "task": {"type": "string"},
                "quantity": {"type": "integer"},
                "site": {"type": ["string", "null"], "description": "Specific customer site; null when not given"},
                "parts_supplier": {"type": "string", "enum": ["unknown", "customer", "supplier"]},
            },
            "required": ["country", "equipment", "task", "quantity", "site", "parts_supplier"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "analyze_flotation",
        "description": "Descriptive analysis ONLY from the supplied hourly flotation CSV for iron/silica concentrate values. Do not infer contractual acceptance, process causality, or equipment guarantees.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "silica_pct": {"type": "number", "description": "Observed % silica in concentrate"},
                "iron_pct": {"type": "number", "description": "Observed % iron in concentrate"},
            },
            "required": ["silica_pct", "iron_pct"],
            "additionalProperties": False,
        },
    },
]


class LocalTools:
    """Read-only local evidence tools. Keeps Stage 03 and Stage 05 logic unchanged."""

    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self._searcher: ProductSearcher | None = None
        self._ledger: list[dict] | None = None

    def search_product_brochures(self, query: str) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Product query must contain 1-2000 characters")
        if self._searcher is None:
            chunks = load_brochures(self.root / "raw" / "data" / "brochures")
            self._searcher = ProductSearcher(chunks)
        hits = self._searcher.search(query, top_k=5)
        return {
            "status": "EVIDENCE_FOUND" if hits else "INSUFFICIENT",
            "items": [
                {
                    "source_id": hit.evidence.source.document_id,
                    "page": hit.evidence.source.page_number,
                    "chunk_id": hit.evidence.chunk_id,
                    "score": round(hit.score, 4),
                    # Deliberately bounded excerpts; no whole PDF or Markdown is uploaded.
                    "excerpt": hit.evidence.excerpt[:650],
                }
                for hit in hits
            ],
            "notice": "Search similarity is not proof of technical suitability, performance guarantees or exact installation compatibility.",
        }

    def compare_service_costs(
        self, country: str, equipment: str, task: str,
        quantity: int, site: str | None, parts_supplier: str,
    ) -> dict:
        if not all(isinstance(x, str) for x in (country, equipment, task)):
            raise ValueError("Invalid request fields")
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise ValueError("Quantity must be an integer")
        if any(len(x) > 200 for x in (country, equipment, task)):
            raise ValueError("A request field is too long")
        if site is not None and (not isinstance(site, str) or len(site) > 200):
            raise ValueError("Invalid site")
        req = ServiceRequest(country, equipment, task, quantity, site, parts_supplier)
        if self._ledger is None:
            self._ledger = load_ledger(self.root / "local_cache" / "service_ledger.json")
        result = build_planning_comparison(
            self._ledger, req, self.root / "raw" / "data" / "HistoricalServices"
        )
        best = result.get("best_historical_analog")
        # Omit customer names/raw bodies. Retain traceable cost items and notices.
        return {
            "status": result["status"],
            "site_specific_budget": result["site_specific_budget"],
            "task_analogs": result["task_analogs"][:4],
            "best_historical_analog": best,
            "local_historical_rates_other_scopes": result[
                "local_historical_rates_other_scopes"
            ][:5],
            "questions": result["questions"],
            "warnings": result["warnings"],
        }

    def analyze_flotation(self, silica_pct: float, iron_pct: float) -> dict:
        return analyze_csv(
            self.root / "raw" / "data" / "flotation_process_data_hourly.csv",
            silica_pct, iron_pct,
        )

    def dispatch(self, name: str, arguments: dict) -> dict:
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        if name == "search_product_brochures":
            if set(arguments) != {"query"}:
                raise ValueError("Invalid product tool arguments")
            return self.search_product_brochures(**arguments)
        if name == "compare_service_costs":
            expected = {"country", "equipment", "task", "quantity", "site", "parts_supplier"}
            if set(arguments) != expected:
                raise ValueError("Invalid service tool arguments")
            return self.compare_service_costs(**arguments)
        if name == "analyze_flotation":
            if set(arguments) != {"silica_pct", "iron_pct"}:
                raise ValueError("Invalid flotation tool arguments")
            return self.analyze_flotation(**arguments)
        raise ValueError("Tool is not on the allowlist")
