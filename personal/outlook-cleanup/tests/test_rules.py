from pathlib import Path

from outlook_cleanup import rules
from outlook_cleanup.models import RuleSet


def test_load_missing_returns_empty(tmp_path: Path):
    assert rules.load(tmp_path / "nope.yaml") == RuleSet()


def test_keep_sender_wins_over_purge_domain(message_factory):
    rs = RuleSet(
        keep_senders={"alice@example.com"},
        purge_domains={"example.com"},
    )
    decision = rules.match(message_factory(sender="alice@example.com"), rs)
    assert decision is not None
    assert decision.verdict == "keep"
    assert decision.classifier == "rule_keep"


def test_purge_domain_matches(message_factory):
    rs = RuleSet(purge_domains={"spam.example"})
    decision = rules.match(message_factory(sender="news@spam.example"), rs)
    assert decision is not None
    assert decision.verdict == "purge"
    assert "spam.example" in decision.reason


def test_purge_subject_regex(message_factory):
    rs = RuleSet(purge_subject_patterns=[r"^\[ADVERT\]"])
    decision = rules.match(message_factory(subject="[ADVERT] Hot deals"), rs)
    assert decision is not None
    assert decision.verdict == "purge"
    assert decision.classifier == "rule_purge"


def test_no_match_returns_none(message_factory):
    assert rules.match(message_factory(), RuleSet()) is None


def test_promote_new_domain():
    rs = RuleSet()
    assert rules.promote(rs, "domain:marketing.example") is True
    assert "marketing.example" in rs.purge_domains
    # idempotent
    assert rules.promote(rs, "domain:marketing.example") is False


def test_promote_subject_keeps_case():
    rs = RuleSet()
    assert rules.promote(rs, r"subject:^\[ADVERT\]") is True
    assert r"^\[ADVERT\]" in rs.purge_subject_patterns


def test_roundtrip_save_load(tmp_path: Path):
    rs = RuleSet(
        keep_senders={"keep@example.com"},
        purge_domains={"spam.example"},
        purge_subject_patterns=["sale"],
    )
    path = tmp_path / "rules.yaml"
    rules.save(path, rs)
    loaded = rules.load(path)
    assert loaded.keep_senders == {"keep@example.com"}
    assert loaded.purge_domains == {"spam.example"}
    assert loaded.purge_subject_patterns == ["sale"]


def test_invalid_regex_skipped(message_factory):
    rs = RuleSet(purge_subject_patterns=["[unclosed"])
    assert rules.match(message_factory(subject="[unclosed bracket"), rs) is None
