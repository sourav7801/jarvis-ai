"""Multi-track, citation-preserving venture evidence collection.

This module turns Company OS research tracks into bounded queries and a source
ledger.  It does not convert snippets into facts or forecast future demand.
Evidence quality is derived only from retrieval metadata supplied by the web
research agent.
"""

from __future__ import annotations

import re
from typing import Any, Callable


ResearchFunction = Callable[[str], dict[str, Any]]


def _clean(value: Any, maximum: int = 2_000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


def build_research_queries(plan: dict[str, Any]) -> list[dict[str, str]]:
    idea = _clean(plan.get("idea"), 1_000)
    tracks = list((plan.get("research_program") or {}).get("research_tracks") or [])
    queries: list[dict[str, str]] = []
    for track in tracks:
        questions = list(track.get("questions") or [])
        source_types = ", ".join(str(item) for item in track.get("evidence_sources") or [])
        queries.append(
            {
                "track_id": str(track.get("id") or "UNKNOWN"),
                "title": _clean(track.get("title"), 180),
                "query": (
                    f"research current evidence for {idea}: {track.get('title')}. "
                    f"Key question: {questions[0] if questions else 'What evidence is available?'}. "
                    f"Prefer primary and authoritative sources such as {source_types or 'public datasets and official documentation'}"
                )[:1_800],
            }
        )
    queries.append(
        {
            "track_id": "OPPORTUNITY_RADAR",
            "title": "Current cross-market opportunity signals",
            "query": (
                "research current global primary-source evidence for persistent costly workarounds, "
                "regulatory or standards transitions, falling enabling technology costs, unmet "
                "accessibility or climate needs, and measurable fragmented-market quality gaps. "
                "Return evidence only; do not predict winners or invent future demand."
            ),
        }
    )
    return queries


def _evidence_grade(source: dict[str, Any]) -> str:
    read_status = str(source.get("read_status") or "").upper()
    provider = str(source.get("provider") or "").upper()
    if read_status in {"EXTRACTED", "READ", "VERIFIED"}:
        return "RETRIEVED_TEXT"
    if provider in {"DIRECT_WEBSITE", "NIRF_GOV_IN"} and source.get("excerpt"):
        return "RETRIEVED_TEXT"
    return "DISCOVERY_LEAD"


def run_venture_evidence_program(
    plan: dict[str, Any],
    research: ResearchFunction,
) -> dict[str, Any]:
    """Collect multi-track evidence while preserving provenance and failures."""

    queries = build_research_queries(plan)
    sources_by_url: dict[str, dict[str, Any]] = {}
    track_rows: list[dict[str, Any]] = []
    providers: set[str] = set()

    for query in queries:
        try:
            result = research(query["query"])
            raw_sources = list(result.get("sources") or [])
            result_providers = result.get("providers") or []
            providers.update(str(item) for item in result_providers if item)
            track_urls: list[str] = []
            for source in raw_sources[:10]:
                url = _clean(source.get("url"), 2_000)
                if not url or not url.lower().startswith(("http://", "https://")):
                    continue
                track_urls.append(url)
                provider = _clean(source.get("provider") or "PUBLIC_WEB", 80)
                providers.add(provider)
                current = sources_by_url.get(url)
                normalized = {
                    "url": url,
                    "title": _clean(source.get("title") or "Public source", 300),
                    "excerpt": _clean(source.get("excerpt"), 2_000),
                    "provider": provider,
                    "read_status": _clean(source.get("read_status") or "UNKNOWN", 80),
                    "evidence_grade": _evidence_grade(source),
                    "tracks": sorted(
                        set((current or {}).get("tracks") or []).union({query["track_id"]})
                    ),
                }
                if current and current.get("evidence_grade") == "RETRIEVED_TEXT":
                    normalized["evidence_grade"] = "RETRIEVED_TEXT"
                sources_by_url[url] = normalized
            track_rows.append(
                {
                    "track_id": query["track_id"],
                    "title": query["title"],
                    "query": query["query"],
                    "status": "EVIDENCE_FOUND" if track_urls else "EVIDENCE_GAP",
                    "source_urls": list(dict.fromkeys(track_urls)),
                    "notice": _clean(result.get("notice"), 800),
                }
            )
        except Exception as error:
            track_rows.append(
                {
                    "track_id": query["track_id"],
                    "title": query["title"],
                    "query": query["query"],
                    "status": "FAILED_SAFE",
                    "source_urls": [],
                    "notice": f"{type(error).__name__}: research provider failed safely.",
                }
            )

    sources = list(sources_by_url.values())
    retrieved = sum(1 for source in sources if source["evidence_grade"] == "RETRIEVED_TEXT")
    covered = sum(1 for row in track_rows if row["status"] == "EVIDENCE_FOUND")
    return {
        "schema_version": 1,
        "truth_policy": "SOURCES_ARE_EVIDENCE_INPUTS_NOT_AUTOMATIC_FACTS",
        "status": (
            "EVIDENCE_READY_FOR_REVIEW"
            if retrieved and covered == len(track_rows)
            else "PARTIAL_EVIDENCE_REQUIRES_REVIEW"
            if sources
            else "DEGRADED_NO_CITABLE_EVIDENCE"
        ),
        "track_count": len(track_rows),
        "covered_tracks": covered,
        "source_count": len(sources),
        "retrieved_text_sources": retrieved,
        "discovery_leads": len(sources) - retrieved,
        "providers": sorted(providers),
        "tracks": track_rows,
        "sources": sources,
        "opportunity_radar": {
            "status": next(
                (row["status"] for row in track_rows if row["track_id"] == "OPPORTUNITY_RADAR"),
                "NOT_RUN",
            ),
            "interpretation": "A human or specialist must test timing, reachability, feasibility, economics, safety and regulatory path before treating any source as a business opportunity.",
        },
        "external_actions_executed": False,
    }

