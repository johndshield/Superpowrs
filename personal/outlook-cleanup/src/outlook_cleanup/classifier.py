from __future__ import annotations

import hashlib
from typing import Iterable

from outlook_cleanup.llm import Classifier as LLMClassifier
from outlook_cleanup.models import Decision, LLMVerdict, Message, RuleSet
from outlook_cleanup.rules import match as rule_match


class Pipeline:
    def __init__(self, rules: RuleSet, llm: LLMClassifier):
        self._rules = rules
        self._llm = llm
        self._cache: dict[str, LLMVerdict] = {}

    def classify(self, message: Message) -> Decision:
        ruled = rule_match(message, self._rules)
        if ruled is not None:
            return ruled

        key = _cache_key(message)
        cached = self._cache.get(key)
        if cached is None:
            cached = self._llm.classify(message)
            self._cache[key] = cached

        return Decision(
            message=message,
            verdict=cached.verdict,
            classifier="llm",
            reason=cached.reason,
            suggested_rule=cached.suggested_rule,
        )

    def classify_many(self, messages: Iterable[Message]) -> list[Decision]:
        return [self.classify(m) for m in messages]


def _cache_key(message: Message) -> str:
    h = hashlib.sha1(message.subject.encode("utf-8")).hexdigest()[:10]
    return f"{message.sender.address}|{h}"
