from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


HttpPost = Callable[
    [str, bytes, dict[str, str], float],
    bytes,
]


def default_http_post(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        return response.read()


ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
        },
        "explanation": {
            "type": "string",
        },
        "confidence": {
            "type": "string",
            "enum": [
                "high",
                "medium",
                "low",
            ],
        },
        "limitations": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": [
        "answer",
        "explanation",
        "confidence",
        "limitations",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class OllamaClient:
    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 300.0
    http_post: HttpPost = default_http_post

    def structured_answer(
        self,
        *,
        question: str,
        evidence_text: str,
    ) -> dict[str, Any]:
        if not question.strip():
            raise ValueError(
                "Question cannot be blank."
            )

        if not evidence_text.strip():
            raise ValueError(
                "Evidence text cannot be blank."
            )

        prompt = f"""
QUESTION:
{question.strip()}

VERIFIED EVIDENCE:
{evidence_text.strip()}

INSTRUCTIONS:
Use only the verified evidence above.
Do not introduce facts from memory.
Preserve units, dates and uncertainty.
If the evidence is insufficient, say so.
Return JSON matching the supplied schema.
""".strip()

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a trust-first "
                        "energy research analyst."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "format": ANSWER_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }

        try:
            body = self.http_post(
                (
                    self.base_url.rstrip("/")
                    + "/api/chat"
                ),
                json.dumps(payload).encode(
                    "utf-8"
                ),
                {
                    "Content-Type": (
                        "application/json"
                    ),
                    "Accept": "application/json",
                },
                self.timeout_seconds,
            )

            response_payload = json.loads(
                body.decode(
                    "utf-8",
                    errors="replace",
                )
            )

            content = response_payload[
                "message"
            ]["content"]

            result = json.loads(content)

        except Exception as exc:
            raise OllamaError(
                f"Ollama request failed: {exc}"
            ) from exc

        required = {
            "answer",
            "explanation",
            "confidence",
            "limitations",
        }

        missing = required - result.keys()

        if missing:
            raise OllamaError(
                "Ollama response is missing: "
                + ", ".join(sorted(missing))
            )

        if result["confidence"] not in {
            "high",
            "medium",
            "low",
        }:
            raise OllamaError(
                "Ollama returned invalid confidence."
            )

        return result
