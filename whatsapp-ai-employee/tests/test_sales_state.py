"""Sales stage derivation and next-step selection.

The requirement: "talks like an actual sales person that catches up, processes,
and proceeds to the next step, asks the right question at the right time."

Retrieval quality cannot produce that. It needs the bot to know *where the
conversation is*. Stage is derived from live facts rather than stored, so it can
never drift out of sync with the order record.
"""

from app.pipeline.sales_state import NEXT_ACTION, STAGE_CTA, SalesContext, Stage


def ctx(stage: Stage, **kw) -> SalesContext:
    return SalesContext(stage=stage, next_action=NEXT_ACTION[stage], **kw)


class TestEveryStageHasAGoal:
    def test_all_stages_have_next_action(self):
        for stage in Stage:
            assert stage in NEXT_ACTION
            assert NEXT_ACTION[stage].strip()

    def test_all_stages_have_cta_entry(self):
        for stage in Stage:
            assert stage in STAGE_CTA  # may be None, but must be considered


class TestNoUpsellOverPendingOrder:
    """A salesperson does not pitch while an order is unresolved."""

    def test_ordered_stage_has_no_cta(self):
        assert STAGE_CTA[Stage.ORDERED] is None

    def test_ordered_goal_is_reassurance(self):
        goal = NEXT_ACTION[Stage.ORDERED].lower()
        assert "reassure" in goal or "existing order" in goal

    def test_confirming_stage_asks_only_for_a_decision(self):
        cta = STAGE_CTA[Stage.CONFIRMING].lower()
        assert "yes" in cta and "no" in cta


class TestSingleQuestionStages:
    """Mid-flow, the slot question IS the call to action — no extra CTA."""

    def test_profiling_has_no_extra_cta(self):
        assert STAGE_CTA[Stage.PROFILING] is None

    def test_configuring_has_no_extra_cta(self):
        assert STAGE_CTA[Stage.CONFIGURING] is None

    def test_intake_goal_forbids_double_questions(self):
        assert "two" in NEXT_ACTION[Stage.PROFILING].lower()


class TestPromptBlock:
    def test_includes_stage_and_goal(self):
        block = ctx(Stage.INTERESTED, last_product="Argan Repair Hair Oil").as_prompt_block()
        assert "interested" in block
        assert "Argan Repair Hair Oil" in block

    def test_known_facts_are_marked_do_not_reask(self):
        block = ctx(Stage.CONFIGURING, known={"pincode": "600066", "name": "Raveen"}).as_prompt_block()
        assert "600066" in block
        assert "not ask again" in block.lower()

    def test_open_order_is_surfaced(self):
        block = ctx(Stage.ORDERED, open_order="ORD123 (pending)").as_prompt_block()
        assert "ORD123" in block

    def test_repeat_customer_flagged(self):
        block = ctx(Stage.POST_PURCHASE, order_count=3).as_prompt_block()
        assert "3" in block

    def test_empty_context_still_produces_a_goal(self):
        block = ctx(Stage.NEW).as_prompt_block()
        assert "GOAL" in block


class TestCtaProperty:
    def test_interested_invites_order(self):
        assert "order" in ctx(Stage.INTERESTED).cta.lower()

    def test_post_purchase_invites_reorder(self):
        assert "reorder" in ctx(Stage.POST_PURCHASE).cta.lower()

    def test_ordered_returns_none(self):
        assert ctx(Stage.ORDERED).cta is None
