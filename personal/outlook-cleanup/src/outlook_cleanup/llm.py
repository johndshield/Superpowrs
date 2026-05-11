from __future__ import annotations

import json
from typing import Protocol

import anthropic

from outlook_cleanup.models import LLMVerdict, Message

SYSTEM_TMPL = """You classify emails as KEEP or PURGE for the user's inbox cleanup.

The user's preferences:
{preferences}

Suggested-rule guidance: if you say PURGE and the unwantedness clearly generalizes, propose ONE rule:
  - "sender:<email>"  for a specific sender that should always purge
  - "domain:<host>"   for a whole sender domain
  - "subject:<regex>" for a subject pattern (Python regex, case-insensitive)
Use null when no rule generalizes safely.

Reply with ONLY a JSON object on a single line:
{{"verdict": "keep" | "purge", "reason": "<short reason>", "suggested_rule": "<rule or null>"}}
"""


class Classifier(Protocol):
    def classify(self, message: Message) -> LLMVerdict: ...


class AnthropicClassifier:
    def __init__(self, *, api_key: str, model: str, preferences: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_TMPL.format(preferences=preferences),
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def classify(self, message: Message) -> LLMVerdict:
        user_msg = (
            f"From: {message.sender.name or ''} <{message.sender.address}>\n"
            f"Subject: {message.subject}\n"
            f"Received: {message.received_at.isoformat()}\n"
            f"Tab: {message.inference_classification}\n"
            f"Preview (truncated to 500 chars):\n{message.body_preview[:500]}"
        )
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=200,
            system=self._system_blocks,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
        return _parse(text)


def _parse(text: str) -> LLMVerdict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in LLM response: {text!r}")
    payload = json.loads(text[start : end + 1])
    if payload.get("suggested_rule") in ("null", ""):
        payload["suggested_rule"] = None
    return LLMVerdict(**payload)
