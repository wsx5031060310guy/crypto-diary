"""Thin client for the local AI Smart Router.

All new LLM calls in this Streamlit app should go through here so
model selection, tier routing, and rate-limit fallback live in one place.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

ROUTER_URL = os.environ.get("SMART_ROUTER_URL", "http://127.0.0.1:8765")
DEFAULT_TIMEOUT = 30.0


@dataclass
class ChatResult:
    content: str
    model: str
    raw: dict


def _pick_model(tier: str) -> str:
    r = httpx.get(f"{ROUTER_URL}/route", params={"tier": tier}, timeout=10.0)
    r.raise_for_status()
    return r.json()["model"]


def chat(
    messages: list[dict],
    *,
    tier: str = "daily",
    model: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> ChatResult:
    chosen = model or _pick_model(tier)
    r = httpx.post(
        f"{ROUTER_URL}/v1/chat/completions",
        json={"model": chosen, "messages": messages},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return ChatResult(content=content, model=chosen, raw=data)
