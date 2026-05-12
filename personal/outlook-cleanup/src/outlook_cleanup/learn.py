from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from outlook_cleanup.models import Message, RuleSet


@dataclass
class LearnResult:
    new_senders: list[str]
    new_domains: list[str]
    scanned: int
    skipped_allow_listed: list[str]


def learn_from_purged(
    messages: Iterable[Message],
    rules: RuleSet,
    *,
    min_occurrences: int = 2,
) -> LearnResult:
    """Add senders/domains seen >= min_occurrences times to rules.purge_*.

    Mutates rules in place. Skips anything already in keep-* or purge-* lists.
    Returns a summary of what changed.
    """
    sender_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    scanned = 0

    for msg in messages:
        scanned += 1
        addr = msg.sender.address.lower()
        if addr:
            sender_counts[addr] += 1
        dom = msg.sender.domain
        if dom:
            domain_counts[dom] += 1

    new_senders: list[str] = []
    new_domains: list[str] = []
    skipped_allow_listed: list[str] = []

    for sender, count in sender_counts.items():
        if count < min_occurrences:
            continue
        if sender in rules.keep_senders:
            skipped_allow_listed.append(f"sender:{sender}")
            continue
        if sender in rules.purge_senders:
            continue
        rules.purge_senders.add(sender)
        new_senders.append(sender)

    for domain, count in domain_counts.items():
        if count < min_occurrences:
            continue
        if domain in rules.keep_domains:
            skipped_allow_listed.append(f"domain:{domain}")
            continue
        if domain in rules.purge_domains:
            continue
        rules.purge_domains.add(domain)
        new_domains.append(domain)

    return LearnResult(
        new_senders=sorted(new_senders),
        new_domains=sorted(new_domains),
        scanned=scanned,
        skipped_allow_listed=sorted(skipped_allow_listed),
    )
