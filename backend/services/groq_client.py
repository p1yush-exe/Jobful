"""Lightweight raw Groq HTTP client used by job_gate.py.
The main CV pipeline uses langchain-groq; this is a dependency-free alternative for job evaluation.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GroqClientError(RuntimeError):
    pass


def call_groq_json(prompt: str, model: str = "llama-3.3-70b-versatile", timeout: int = 30) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise GroqClientError("GROQ_API_KEY is missing.")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise GroqClientError(f"groq_http_{exc.code}:{body_text[:300]}") from exc
    except URLError as exc:
        raise GroqClientError(f"groq_network_error:{exc.reason}") from exc

    try:
        content = raw["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        raise GroqClientError(f"groq_invalid_response:{raw}") from exc
