"""Regression tests for the cascade's cost behaviour.

These exist because of a real bug: the LLM router originally ran BEFORE keyword
search, so every non-smalltalk message cost a model call even when a free FAQ
match was available. That defeats the entire point of the cascade and burns
through a free-tier quota in seconds.
"""

import inspect

from app.pipeline import orchestrator


def _source() -> str:
    return inspect.getsource(orchestrator.process_message)


class TestCascadeOrdering:
    def test_fast_path_runs_before_router(self):
        src = _source()
        fast_path_pos = src.index("try_fast_path")
        router_pos = src.index("router.route")
        assert fast_path_pos < router_pos, (
            "keyword fast path must run before the LLM router, otherwise every "
            "message costs a model call"
        )

    def test_intent_gate_runs_before_faq_lookup(self):
        """A transactional intent must outrank a keyword match.

        Regression: "where is my order" was answered by the delivery-charges FAQ,
        because that FAQ's text contains the word "orders" and the FAQ lookup ran
        first. Deterministic intent classification is both more correct here and
        cheaper (regex vs a database query).
        """
        src = _source()
        assert src.index("fast_intent.classify") < src.index("try_fast_path")

    def test_faq_gated_on_intent(self):
        src = _source()
        assert "faq_eligible" in src
        assert 'fast.intent == "catalog_qa"' in src

    def test_guardrails_run_before_any_model_call(self):
        src = _source()
        assert src.index("check_inbound") < src.index("router.route")

    def test_smalltalk_runs_before_cache_and_router(self):
        src = _source()
        assert src.index("detect_smalltalk") < src.index("router.route")

    def test_cache_lookup_runs_before_router(self):
        src = _source()
        assert src.index("get_answer") < src.index("router.route")


class TestDegradation:
    def test_router_failure_falls_back_to_heuristic(self):
        """A provider 429 must not escalate every message to a human."""
        src = _source()
        assert "decision.failed" in src
        assert "heuristic_route" in src

    def test_low_confidence_tries_retrieval_before_escalating(self):
        src = _source()
        assert "low_confidence_fallthrough" in src

    def test_mid_flow_skips_fast_path(self):
        """A message during order capture is an answer, not a new query."""
        src = _source()
        assert "not active_flow" in src
        assert "faq_eligible" in src


class TestHeuristicRouter:
    def test_order_intent(self):
        assert orchestrator.heuristic_route("i want to order shampoo", {}) == "order_capture"

    def test_status_intent(self):
        assert orchestrator.heuristic_route("where is my order", {}) == "order_status"

    def test_consultation_intent(self):
        assert (
            orchestrator.heuristic_route("can you suggest something for dandruff", {})
            == "consultation"
        )

    def test_default_is_catalog_qa(self):
        assert orchestrator.heuristic_route("price of argan oil", {}) == "catalog_qa"

    def test_active_order_flow_wins(self):
        # Mid-order, a bare pincode must continue the order, not be re-routed.
        assert orchestrator.heuristic_route("641002", {"flow": "order"}) == "order_capture"
        assert (
            orchestrator.heuristic_route("12 Gandhi Street", {"flow": "order"})
            == "order_capture"
        )
