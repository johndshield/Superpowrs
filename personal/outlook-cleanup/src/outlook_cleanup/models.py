from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Verdict = Literal["keep", "purge"]
Classifier = Literal["rule_keep", "rule_purge", "llm"]
Action = Literal["moved", "skipped", "declined", "kept", "failed"]


class EmailAddress(BaseModel):
    name: str | None = None
    address: str

    @property
    def domain(self) -> str:
        return self.address.rsplit("@", 1)[-1].lower() if "@" in self.address else ""


class Message(BaseModel):
    id: str
    subject: str = ""
    sender: EmailAddress
    body_preview: str = ""
    received_at: datetime
    is_read: bool = False
    inference_classification: Literal["focused", "other"] = "focused"
    has_attachments: bool = False

    @classmethod
    def from_graph(cls, raw: dict) -> "Message":
        from_field = raw.get("from") or raw.get("sender") or {}
        addr = (from_field.get("emailAddress") or {}) if isinstance(from_field, dict) else {}
        return cls(
            id=raw["id"],
            subject=raw.get("subject") or "",
            sender=EmailAddress(
                name=addr.get("name"),
                address=(addr.get("address") or "").lower(),
            ),
            body_preview=raw.get("bodyPreview") or "",
            received_at=raw["receivedDateTime"],
            is_read=raw.get("isRead", False),
            inference_classification=raw.get("inferenceClassification", "focused"),
            has_attachments=raw.get("hasAttachments", False),
        )


class Decision(BaseModel):
    message: Message
    verdict: Verdict
    classifier: Classifier
    reason: str
    suggested_rule: str | None = None
    action: Action = "skipped"


class RuleSet(BaseModel):
    keep_senders: set[str] = Field(default_factory=set)
    keep_domains: set[str] = Field(default_factory=set)
    purge_senders: set[str] = Field(default_factory=set)
    purge_domains: set[str] = Field(default_factory=set)
    purge_subject_patterns: list[str] = Field(default_factory=list)


class LLMVerdict(BaseModel):
    verdict: Verdict
    reason: str
    suggested_rule: str | None = None
