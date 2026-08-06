from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

from prompting import build_research_prompt
from source_registry import classify_intent, domains_for_intent

from market_intelligence.api.adapter import (
    cited_answer_to_response,
    universal_answer_to_response,
)
from market_intelligence.api.models import (
    EnergyCapabilityResponse,
    EnergySearchRequest,
    EnergySearchResponse,
    EnergyStatusResponse,
)
from market_intelligence.service.cited_research_service import (
    default_cited_research_service,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalResearchOrchestrator,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Energy Market Intelligence",
    version="4.0.0",
    description=(
        "Trust-first energy-market search API using "
        "official structured data and controlled "
        "web-research fallback."
    ),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_universal_orchestrator = UniversalResearchOrchestrator()

_cited_research_service = (
    default_cited_research_service()
)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)
    mode: str = Field(default="standard", pattern="^(standard|deep)$")


class AskResponse(BaseModel):
    answer: str
    intent: str
    searched_at_pt: str
    citations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    used_fallback_search: bool


def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server.",
        )
    return OpenAI(api_key=key)


def _extract_response_data(response: Any) -> tuple[str, list[dict], list[dict]]:
    data = response.model_dump() if hasattr(response, "model_dump") else response

    answer = ""
    citations: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []

    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    answer += content.get("text", "")
                    for ann in content.get("annotations", []) or []:
                        if ann.get("type") == "url_citation":
                            citations.append({
                                "url": ann.get("url"),
                                "title": ann.get("title") or ann.get("url"),
                                "start_index": ann.get("start_index"),
                                "end_index": ann.get("end_index"),
                            })

        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for src in action.get("sources", []) or []:
                url = src.get("url")
                if url:
                    all_sources.append({
                        "url": url,
                        "title": src.get("title") or url,
                        "type": src.get("type"),
                    })

    # Deduplicate while preserving order.
    def unique(rows: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for row in rows:
            url = row.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(row)
        return out

    return answer.strip(), unique(citations), unique(all_sources)


def _search(
    *,
    question: str,
    intent: str,
    now_pt: str,
    allowed_domains: list[str] | None,
    mode: str,
) -> Any:
    tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": "high" if mode == "deep" else "medium",
    }
    if allowed_domains:
        tool["filters"] = {"allowed_domains": allowed_domains}

    kwargs: dict[str, Any] = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6"),
        "tools": [tool],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "input": build_research_prompt(
            question,
            now_pt=now_pt,
            intent=intent,
        ),
    }

    if mode == "deep":
        kwargs["reasoning"] = {"effort": "high"}

    return _client().responses.create(**kwargs)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "CAISO Market Intelligence V3"}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    question = req.question.strip()
    intent = classify_intent(question)
    domains = domains_for_intent(intent)
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    now_pt = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Pass 1: high-authority domain-constrained research.
    response = _search(
        question=question,
        intent=intent,
        now_pt=now_pt,
        allowed_domains=domains,
        mode=req.mode,
    )
    answer, citations, sources = _extract_response_data(response)

    # Fallback: if constrained research produced weak/no source evidence,
    # broaden the web rather than fabricate an answer.
    used_fallback = False
    if not answer or (len(citations) < 1 and len(sources) < 2):
        used_fallback = True
        response = _search(
            question=question,
            intent=intent,
            now_pt=now_pt,
            allowed_domains=None,
            mode=req.mode,
        )
        answer, citations, sources = _extract_response_data(response)

    if not answer:
        raise HTTPException(
            status_code=502,
            detail="Research completed but no answer text was returned.",
        )

    return AskResponse(
        answer=answer,
        intent=intent,
        searched_at_pt=now_pt,
        citations=citations,
        sources=sources,
        used_fallback_search=used_fallback,
    )


@app.get(
    "/api/status",
    response_model=EnergyStatusResponse,
)
def api_status() -> EnergyStatusResponse:
    return EnergyStatusResponse(
        status="ok",
        service="Energy Market Intelligence",
        version="4.0.0",
        universal_orchestrator=True,
        eia_cache_available=(
            BASE_DIR
            / ".cache"
            / "eia"
            / "EBA.zip"
        ).exists(),
        openai_configured=bool(
            os.getenv("OPENAI_API_KEY")
        ),
    )


@app.get(
    "/api/capabilities",
    response_model=list[EnergyCapabilityResponse],
)
def api_capabilities() -> list[
    EnergyCapabilityResponse
]:
    return [
        EnergyCapabilityResponse(
            capability="CAISO market prices",
            status="live",
            controlling_source="CAISO OASIS",
            examples=[
                (
                    "What were NP-15 day-ahead "
                    "prices yesterday?"
                ),
            ],
        ),
        EnergyCapabilityResponse(
            capability="ISO operating data",
            status="live_with_local_cache",
            controlling_source="EIA Form EIA-930",
            examples=[
                "What is CAISO demand right now?",
                "What is ERCOT demand?",
                "What is PJM net generation?",
            ],
        ),
        EnergyCapabilityResponse(
            capability="Nuclear reactor status",
            status="live",
            controlling_source="U.S. NRC",
            examples=[
                (
                    "Is Diablo Canyon running at "
                    "full capacity?"
                ),
            ],
        ),
        EnergyCapabilityResponse(
            capability="Universal energy research",
            status="research_fallback",
            controlling_source=(
                "Approved official and high-authority "
                "web sources"
            ),
            examples=[
                (
                    "Why did Henry Hub natural-gas "
                    "prices rise?"
                ),
                (
                    "What new FERC orders affect "
                    "transmission planning?"
                ),
            ],
        ),
    ]


@app.post(
    "/api/search",
    response_model=EnergySearchResponse,
)
def energy_search(
    req: EnergySearchRequest,
) -> EnergySearchResponse:
    question = req.question.strip()

    try:
        result = _universal_orchestrator.answer(
            question
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EIA_CACHE_NOT_AVAILABLE",
                "message": str(exc),
                "remediation": (
                    "Refresh the official EIA EBA "
                    "cache before requesting operating "
                    "data."
                ),
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "STRUCTURED_EXECUTOR_FAILURE",
                "message": str(exc),
            },
        ) from exc

    result_status = str(
        getattr(
            result.status,
            "value",
            result.status,
        )
    )

    if (
        result_status == "research_required"
        and req.allow_web_fallback
    ):
        try:
            cited_answer = (
                _cited_research_service.answer(
                    question
                )
            )

        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": (
                        "CITED_RESEARCH_FAILURE"
                    ),
                    "message": str(exc),
                },
            ) from exc

        domain = str(
            getattr(
                result.domain,
                "value",
                result.domain,
            )
        )

        return cited_answer_to_response(
            cited_answer,
            domain=domain,
        )

    return universal_answer_to_response(
        result
    )
