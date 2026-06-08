from __future__ import annotations

import re
from pathlib import Path

import yaml

from outlook_cleanup.models import Decision, Message, RuleSet


def empty() -> RuleSet:
    return RuleSet()


def load(path: Path) -> RuleSet:
    if not path.exists():
        return empty()
    data = yaml.safe_load(path.read_text()) or {}
    keep = data.get("keep") or {}
    purge = data.get("purge") or {}
    return RuleSet(
        keep_senders={s.lower() for s in keep.get("senders") or []},
        keep_domains={d.lower() for d in keep.get("domains") or []},
        purge_senders={s.lower() for s in purge.get("senders") or []},
        purge_domains={d.lower() for d in purge.get("domains") or []},
        purge_subject_patterns=list(purge.get("subject_patterns") or []),
    )


def save(path: Path, rules: RuleSet) -> None:
    data = {
        "keep": {
            "senders": sorted(rules.keep_senders),
            "domains": sorted(rules.keep_domains),
        },
        "purge": {
            "senders": sorted(rules.purge_senders),
            "domains": sorted(rules.purge_domains),
            "subject_patterns": list(rules.purge_subject_patterns),
        },
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def match(message: Message, rules: RuleSet) -> Decision | None:
    sender = message.sender.address.lower()
    domain = message.sender.domain
    subject = message.subject or ""

    if sender and sender in rules.keep_senders:
        return Decision(
            message=message,
            verdict="keep",
            classifier="rule_keep",
            reason=f"keep-sender: {sender}",
        )
    if domain and domain in rules.keep_domains:
        return Decision(
            message=message,
            verdict="keep",
            classifier="rule_keep",
            reason=f"keep-domain: {domain}",
        )

    if sender and sender in rules.purge_senders:
        return Decision(
            message=message,
            verdict="purge",
            classifier="rule_purge",
            reason=f"purge-sender: {sender}",
        )
    if domain and domain in rules.purge_domains:
        return Decision(
            message=message,
            verdict="purge",
            classifier="rule_purge",
            reason=f"purge-domain: {domain}",
        )
    for pattern in rules.purge_subject_patterns:
        try:
            if re.search(pattern, subject, flags=re.IGNORECASE):
                return Decision(
                    message=message,
                    verdict="purge",
                    classifier="rule_purge",
                    reason=f"purge-subject: {pattern}",
                )
        except re.error:
            continue
    return None


def promote(rules: RuleSet, suggested_rule: str) -> bool:
    """Add a suggested rule. Returns True if it was new."""
    s = suggested_rule.strip().lower()
    if not s:
        return False
    if s.startswith("sender:"):
        val = s[len("sender:"):].strip()
        if val and val not in rules.purge_senders:
            rules.purge_senders.add(val)
            return True
    elif s.startswith("domain:"):
        val = s[len("domain:"):].strip()
        if val and val not in rules.purge_domains:
            rules.purge_domains.add(val)
            return True
    elif s.startswith("subject:"):
        val = suggested_rule.split(":", 1)[1].strip()
        if val and val not in rules.purge_subject_patterns:
            rules.purge_subject_patterns.append(val)
            return True
    return False
