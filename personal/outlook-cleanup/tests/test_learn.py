from outlook_cleanup.learn import learn_from_purged
from outlook_cleanup.models import RuleSet


def test_promotes_domain_when_seen_twice(message_factory):
    msgs = [
        message_factory(sender="a@spam.example", msg_id="m1"),
        message_factory(sender="b@spam.example", msg_id="m2"),
    ]
    rs = RuleSet()
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert "spam.example" in rs.purge_domains
    assert "spam.example" in result.new_domains
    assert result.scanned == 2


def test_promotes_sender_when_seen_twice(message_factory):
    msgs = [
        message_factory(sender="x@a.example", msg_id="m1"),
        message_factory(sender="x@a.example", msg_id="m2"),
    ]
    rs = RuleSet()
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert "x@a.example" in rs.purge_senders
    assert "a.example" in rs.purge_domains  # domain hits threshold too
    assert "x@a.example" in result.new_senders


def test_single_occurrence_is_skipped(message_factory):
    msgs = [message_factory(sender="one@off.example", msg_id="m1")]
    rs = RuleSet()
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert not rs.purge_senders
    assert not rs.purge_domains
    assert result.new_senders == []
    assert result.new_domains == []


def test_allow_listed_sender_is_skipped(message_factory):
    msgs = [
        message_factory(sender="boss@company.com", msg_id="m1"),
        message_factory(sender="boss@company.com", msg_id="m2"),
    ]
    rs = RuleSet(keep_senders={"boss@company.com"})
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert "boss@company.com" not in rs.purge_senders
    assert "sender:boss@company.com" in result.skipped_allow_listed


def test_allow_listed_domain_is_skipped(message_factory):
    msgs = [
        message_factory(sender="a@company.com", msg_id="m1"),
        message_factory(sender="b@company.com", msg_id="m2"),
    ]
    rs = RuleSet(keep_domains={"company.com"})
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert "company.com" not in rs.purge_domains
    assert "domain:company.com" in result.skipped_allow_listed


def test_existing_purge_rule_not_duplicated(message_factory):
    msgs = [
        message_factory(sender="a@known.example", msg_id="m1"),
        message_factory(sender="b@known.example", msg_id="m2"),
    ]
    rs = RuleSet(purge_domains={"known.example"})
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    assert rs.purge_domains == {"known.example"}
    assert result.new_domains == []  # not a "new" addition


def test_mixed_threshold_per_field(message_factory):
    msgs = [
        message_factory(sender="x@bad.example", msg_id="m1"),
        message_factory(sender="x@bad.example", msg_id="m2"),
        message_factory(sender="y@once.example", msg_id="m3"),
    ]
    rs = RuleSet()
    result = learn_from_purged(msgs, rs, min_occurrences=2)
    # x@bad.example seen 2x -> promoted
    assert "x@bad.example" in rs.purge_senders
    # bad.example seen 2x -> promoted
    assert "bad.example" in rs.purge_domains
    # y@once.example and once.example only seen 1x -> skipped
    assert "y@once.example" not in rs.purge_senders
    assert "once.example" not in rs.purge_domains
