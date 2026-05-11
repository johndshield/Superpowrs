from outlook_cleanup.classifier import Pipeline
from outlook_cleanup.models import LLMVerdict, RuleSet


class FakeLLM:
    def __init__(self, verdict: LLMVerdict):
        self.calls = 0
        self._verdict = verdict

    def classify(self, message):
        self.calls += 1
        return self._verdict


def test_rule_match_skips_llm(message_factory):
    rs = RuleSet(purge_domains={"spam.example"})
    llm = FakeLLM(LLMVerdict(verdict="keep", reason="ignored"))
    pipe = Pipeline(rs, llm)

    decision = pipe.classify(message_factory(sender="news@spam.example"))
    assert decision.verdict == "purge"
    assert decision.classifier == "rule_purge"
    assert llm.calls == 0


def test_llm_invoked_when_no_rule(message_factory):
    llm = FakeLLM(
        LLMVerdict(verdict="purge", reason="mass marketing", suggested_rule="domain:promo.example")
    )
    pipe = Pipeline(RuleSet(), llm)

    decision = pipe.classify(message_factory(sender="x@promo.example"))
    assert decision.verdict == "purge"
    assert decision.classifier == "llm"
    assert decision.suggested_rule == "domain:promo.example"
    assert llm.calls == 1


def test_llm_cached_per_sender_subject(message_factory):
    llm = FakeLLM(LLMVerdict(verdict="purge", reason="x"))
    pipe = Pipeline(RuleSet(), llm)

    m1 = message_factory(sender="x@promo.example", subject="Sale!", msg_id="a")
    m2 = message_factory(sender="x@promo.example", subject="Sale!", msg_id="b")
    pipe.classify(m1)
    pipe.classify(m2)
    assert llm.calls == 1


def test_llm_called_again_for_different_subject(message_factory):
    llm = FakeLLM(LLMVerdict(verdict="purge", reason="x"))
    pipe = Pipeline(RuleSet(), llm)

    pipe.classify(message_factory(sender="x@promo.example", subject="Sale!", msg_id="a"))
    pipe.classify(message_factory(sender="x@promo.example", subject="Other", msg_id="b"))
    assert llm.calls == 2
