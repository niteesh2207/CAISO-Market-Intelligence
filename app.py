from __future__ import annotations

import logging
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
    universal_answer_to_response,
)
from market_intelligence.api.models import (
    EnergyCapabilityResponse,
    EnergySearchRequest,
    EnergySearchResponse,
    EnergySourceResponse,
    EnergyStatusResponse,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswerStatus,
    UniversalResearchOrchestrator,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
APP_NAME = "CAISO Market Intelligence"
APP_VERSION = "4.0.0"
logger = logging.getLogger(__name__)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Trust-first energy-market search API using "
        "official structured data and controlled "
        "web-research fallback."
    ),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_universal_orchestrator = UniversalResearchOrchestrator()


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
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }


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
        service=APP_NAME,
        version=APP_VERSION,
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
            status="implemented_live_source",
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
            status="implemented_cache_backed",
            controlling_source="EIA Form EIA-930",
            examples=[
                "What is CAISO demand right now?",
                "What is ERCOT demand?",
                "What is PJM net generation?",
            ],
        ),
        EnergyCapabilityResponse(
            capability="Nuclear reactor status",
            status="implemented_live_source",
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
            status="implemented_controlled_fallback",
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


def _fallback_source_rows(
    citations: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> list[EnergySourceResponse]:
    rows = citations if citations else sources
    return [
        EnergySourceResponse(
            provider="openai_web_search",
            title=str(row.get("title") or row.get("url")),
            url=str(row["url"]),
            primary=False,
            role="supporting",
        )
        for row in rows
        if row.get("url")
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
        result = _universal_orchestrator.answer(question)

    except FileNotFoundError:
        logger.info(
            "Structured operating-data cache was unavailable.",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EIA_CACHE_NOT_AVAILABLE",
                "message": (
                    "The required operating-data cache is "
                    "not available."
                ),
                "remediation": (
                    "Refresh the official EIA cache and retry."
                ),
            },
        ) from None

    except Exception:
        logger.exception("Structured energy executor failed.")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "STRUCTURED_EXECUTOR_FAILURE",
                "message": (
                    "The structured research executor failed."
                ),
            },
        ) from None

    structured = universal_answer_to_response(result)

    if (
        result.status != UniversalAnswerStatus.RESEARCH_REQUIRED
        or not req.allow_web_fallback
    ):
        return structured

    intent = classify_intent(question)
    domains = domains_for_intent(intent)
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    now_pt = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    broadened = False

    try:
        response = _search(
            question=question,
            intent=intent,
            now_pt=now_pt,
            allowed_domains=domains,
            mode="standard",
        )
        answer, citations, sources = _extract_response_data(
            response
        )

        if not answer or (
            len(citations) < 1 and len(sources) < 2
        ):
            broadened = True
            response = _search(
                question=question,
                intent=intent,
                now_pt=now_pt,
                allowed_domains=None,
                mode="standard",
            )
            answer, citations, sources = _extract_response_data(
                response
            )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Controlled web fallback failed.")
        return structured.model_copy(
            update={
                "limitations": [
                    *structured.limitations,
                    (
                        "Controlled web fallback failed; the "
                        "structured research status was preserved."
                    ),
                ]
            }
        )

    if not answer:
        return structured.model_copy(
            update={
                "limitations": [
                    *structured.limitations,
                    (
                        "Controlled web research returned no "
                        "releasable answer."
                    ),
                ]
            }
        )

    return EnergySearchResponse(
        status="answered",
        domain=structured.domain,
        answer=answer,
        explanation=(
            "No live structured executor was available for "
            "this route, so the service used controlled web "
            "research. Review the supporting sources and "
            "limitations before operational use."
        ),
        confidence="medium",
        evidence={
            "fallback_scope": (
                "broadened_web"
                if broadened
                else "authority_constrained_web"
            ),
            "searched_at_pt": now_pt,
        },
        sources=_fallback_source_rows(citations, sources),
        limitations=[
            (
                "Web-research fallback is supporting evidence, "
                "not a substitute for a controlling structured "
                "market-data feed."
            )
        ],
        clarification_options=[],
        route=structured.route,
        used_web_fallback=True,
    )
