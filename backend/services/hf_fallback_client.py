"""HuggingFace Inference API fallback for job_gate.py when Groq is unavailable."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HFFallbackError(RuntimeError):
    pass


def call_hf_json(prompt: str, timeout: int = 40) -> dict[str, Any]:
    api_key = os.getenv("HF_TOKEN", "").strip()
    model = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3").strip()
    if not api_key:
        raise HFFallbackError("HF_TOKEN is missing.")

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 220, "temperature": 0.0, "return_full_text": False},
    }
    request = Request(
        f"https://api-inference.huggingface.co/models/{model}",
        data=json.dumps(payload).encode("utf-8"),
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
        raise HFFallbackError(f"hf_http_{exc.code}:{body_text[:300]}") from exc
    except URLError as exc:
        raise HFFallbackError(f"hf_network_error:{exc.reason}") from exc

    text = ""
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        text = str(raw[0].get("generated_text", "")).strip()
    elif isinstance(raw, dict) and "generated_text" in raw:
        text = str(raw["generated_text"]).strip()
    else:
        raise HFFallbackError(f"hf_invalid_response:{raw}")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise HFFallbackError(f"hf_non_json_output:{text[:250]}")
    try:
        return json.loads(text[start: end + 1])
    except json.JSONDecodeError as exc:
        raise HFFallbackError(f"hf_json_parse_error:{text[:250]}") from exc
