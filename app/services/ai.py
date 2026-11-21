"""JSON chat completions with provider fallback: Gemini first, then Groq.

Both expose OpenAI-compatible APIs, so one client type covers both.
Returns None when every provider fails; callers must have a rules fallback.
"""

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings

log = logging.getLogger(__name__)


def _providers() -> list[tuple[str, AsyncOpenAI, str]]:
    s = get_settings()
    out = []
    # Short timeout + 1 retry: a stuck provider must not hang /today; fall through to the next one.
    opts = {"timeout": 20, "max_retries": 1}
    if s.gemini_api_key:
        out.append(("gemini", AsyncOpenAI(api_key=s.gemini_api_key, base_url=s.gemini_base_url, **opts), s.gemini_model))
    if s.groq_api_key:
        out.append(("groq", AsyncOpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url, **opts), s.groq_model))
    return out


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if m := re.search(r"\{.*\}", text, re.S):  # tolerate ```json fences
        text = m.group(0)
    return json.loads(text)


async def complete_json(system: str, user: str) -> tuple[dict[str, Any], str] | None:
    """Returns (parsed_json, provider_name) or None."""
    for name, client, model in _providers():
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return _parse_json(resp.choices[0].message.content or ""), name
        except Exception as e:  # rate limit, network, bad JSON -> try next provider
            log.warning("AI provider %s failed: %s", name, e)
    return None


def enabled() -> bool:
    return bool(_providers())
