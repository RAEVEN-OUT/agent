"""The cost cascade.

Every inbound message walks these steps in order and returns as soon as one of
them can answer confidently. The LLM is the last resort, not the first move:

    1. normalize + gibberish filter        zero cost
    2. inbound guardrails (safety)         zero cost
    3. small-talk canned replies           zero cost
    4. answer cache (facts only)           zero cost
    5. local follow-up rewrite             zero cost
    6. keyword search (Postgres FTS)       ~milliseconds, no API call
    7. embeddings + Qdrant                 cheap, cached
    8. LLM routing + composition           last

The tier rule: when nothing is confident, Basic hands to the human and Pro
hands to the LLM.
"""

import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import loop as agent_loop
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import PipelineMetrics
from app.db.models import Conversation, Customer, Tenant, UsageLog
from app.modules import catalog_qa, consultation, escalation, order_capture, order_status
from app.pipeline import fast_intent, guardrails, router, sales_state
from app.pipeline.normalize import (
    is_meaningless,
    local_rewrite,
    looks_like_followup,
    looks_like_topic_change,
    normalize,
)
from app.pipeline.smalltalk import canned_reply, detect_smalltalk
from app.services.llm_service import llm_service
from app.services.redis_service import redis_service

log = get_logger("orchestrator")

LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class Outcome:
    reply: str | None = None
    intent: str | None = None
    handled_by: str | None = None
    escalated: bool = False
    silent: bool = False
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)


# --- Basic-plan routing: keywords only, no model call ----------------------

ORDER_WORDS = ("order", "buy", "purchase", "want it", "book", "place order", "i will take")
STATUS_WORDS = ("where is my", "order status", "tracking", "track my", "delivered", "shipped yet")
CONSULT_WORDS = ("suggest", "recommend", "which one", "what should i", "good for")


def heuristic_route(normalized: str, state: dict) -> str:
    if state.get("flow") == "order":
        return "order_capture"
    if any(w in normalized for w in STATUS_WORDS):
        return "order_status"
    if any(w in normalized for w in ORDER_WORDS):
        return "order_capture"
    if any(w in normalized for w in CONSULT_WORDS):
        return "consultation"
    return "catalog_qa"


async def process_message(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    conversation: Conversation,
    *,
    raw_message: str,
    has_media: bool = False,
    entry_context: dict | None = None,
) -> Outcome:
    metrics = PipelineMetrics()
    outcome = Outcome(metrics=metrics)
    tenant_settings = tenant.settings or {}

    # A human already owns this thread — the bot must not talk over them.
    if conversation.human_handoff:
        metrics.mark("path", "human_handoff_silent")
        outcome.silent = True
        return outcome

    # --- step 1: normalize ---
    t0 = time.perf_counter()
    normalized = normalize(raw_message)
    metrics.record("normalize", t0)

    if has_media and not normalized:
        # Photos of hair/scalp are common. We never diagnose from an image.
        reply = await escalation.raise_escalation(
            db, tenant, conversation,
            reason="human_request",
            detail="Customer sent an image with no text.",
            customer_wa_id=customer.wa_id,
        )
        outcome.reply = (
            "Thanks for the photo! I've passed it to our team — they'll take a look "
            "and reply here shortly."
        )
        outcome.escalated = True
        outcome.handled_by = "media_escalation"
        metrics.mark("path", "media_escalation")
        return outcome

    if is_meaningless(normalized):
        metrics.mark("path", "meaningless")
        outcome.reply = tenant_settings.get(
            "fallback_message", "Sorry, I didn't catch that. Could you rephrase?"
        )
        outcome.handled_by = "meaningless_filter"
        return outcome

    # --- step 2: inbound safety guardrails (never auto-answer these) ---
    t0 = time.perf_counter()
    flagged = guardrails.check_inbound(normalized)
    metrics.record("guardrails", t0)
    if flagged:
        reason, phrase = flagged
        metrics.mark("path", "guardrail_escalation")
        metrics.mark("guardrail_reason", reason)
        outcome.reply = await escalation.raise_escalation(
            db, tenant, conversation,
            reason=reason,
            detail=f"matched '{phrase}' in: {raw_message}",
            customer_wa_id=customer.wa_id,
        )
        outcome.escalated = True
        outcome.intent = reason
        outcome.handled_by = "guardrail"
        return outcome

    # --- step 3: small talk (canned, zero cost) ---
    t0 = time.perf_counter()
    small = detect_smalltalk(normalized)
    metrics.record("smalltalk", t0)
    if small:
        metrics.mark("path", "smalltalk")
        if small == "human_request":
            outcome.reply = await escalation.raise_escalation(
                db, tenant, conversation,
                reason="human_request",
                detail=raw_message,
                customer_wa_id=customer.wa_id,
            )
            outcome.escalated = True
        else:
            outcome.reply = canned_reply(small, tenant_settings)
        outcome.intent = small
        outcome.handled_by = "smalltalk"
        return outcome

    # --- step 4: answer cache (facts only; composed sales replies never cached) ---
    cache_key = redis_service.cache_key(str(tenant.id), normalized)
    t0 = time.perf_counter()
    cached = await redis_service.get_answer(cache_key)
    metrics.record("cache_lookup", t0)
    if cached:
        metrics.mark("path", "cache_hit")
        outcome.reply = cached
        outcome.handled_by = "cache"
        return outcome

    # --- step 5: local follow-up rewrite (zero cost) ---
    history = await redis_service.get_history(str(conversation.id))
    search_query = normalized
    if history and looks_like_followup(normalized):
        last_topic = history[-1].get("user", "")
        search_query = local_rewrite(normalized, last_topic)
        metrics.mark("rewritten", True)

    state = dict(conversation.state or {})
    active_flow = state.get("flow")

    # Where is this conversation? Derived from live facts, never stored, so it
    # cannot drift. Every composed reply gets this so it advances the sale
    # instead of answering and stopping.
    sales = await sales_state.derive(
        db, tenant, customer, state, history_len=len(history)
    )
    metrics.mark("sales", sales.as_trace())

    # --- AGENT MODE ---
    # Everything above this line is policy and hygiene: safety guardrails,
    # small talk, cache, idempotency. Those stay deterministic on purpose.
    # Everything below — understanding what the customer meant and deciding what
    # to do next — is handed to the model with tools, because hand-writing it is
    # what produced most of the bugs found in live testing.
    if settings.AGENT_MODE and tenant.is_pro and llm_service.available:
        t0 = time.perf_counter()
        agent_result = await agent_loop.run(
            db=db,
            tenant=tenant,
            customer=customer,
            conversation=conversation,
            message=raw_message,
            history=history,
            sales=sales,
            metrics=metrics,
        )
        metrics.record("agent", t0)
        metrics.mark("tools", agent_result.tool_calls)
        metrics.mark("agent_rounds", agent_result.rounds)
        if agent_result.input_tokens or agent_result.output_tokens:
            metrics.add_usage(agent_result.input_tokens, agent_result.output_tokens)

        if not agent_result.failed and agent_result.reply:
            outcome.reply = agent_result.reply
            outcome.intent = "agent"
            outcome.handled_by = "agent:" + ",".join(agent_result.tool_calls[:4] or ["reply"])

            if agent_result.escalation_reason:
                await escalation.raise_escalation(
                    db, tenant, conversation,
                    reason=agent_result.escalation_reason
                    if agent_result.escalation_reason in escalation.LOCKING_REASONS
                    else "low_confidence",
                    detail=raw_message,
                    customer_wa_id=customer.wa_id,
                )
                outcome.escalated = True

            if metrics.llm_calls:
                db.add(
                    UsageLog(
                        tenant_id=tenant.id, kind="llm",
                        input_tokens=metrics.input_tokens,
                        output_tokens=metrics.output_tokens,
                        units=metrics.llm_calls,
                        meta={"mode": "agent", "tools": agent_result.tool_calls},
                    )
                )
            await redis_service.add_history(
                str(conversation.id), raw_message, outcome.reply
            )
            return outcome

        # Agent failed (quota, empty response, max rounds). Fall through to the
        # deterministic pipeline rather than leaving the customer with silence.
        metrics.mark("agent_degraded", True)

    # --- step 6: deterministic intent gate (pure regex, no DB, no model) ---
    # Runs BEFORE the FAQ lookup. "where is my order" must never be answered by
    # an FAQ that happens to contain the word "orders" — a transactional intent
    # outranks a keyword match, and checking it first is also cheaper than the
    # database query.
    fast = fast_intent.classify(
        normalized, raw_message, state=state, entry_context=entry_context or {}
    )
    if fast:
        metrics.mark("fast_intent", f"{fast.intent}:{fast.reason}")

    # --- step 7: keyword FAQ fast path ---
    # Only when the message is not already claimed by a transactional intent,
    # and not mid-flow (a message during order capture answers our last question
    # rather than asking a new one).
    faq_eligible = not active_flow and (fast is None or fast.intent == "catalog_qa")
    if faq_eligible:
        t0 = time.perf_counter()
        faq_hit = await catalog_qa.try_fast_path(
            db, tenant, normalized=normalized, search_query=search_query, metrics=metrics
        )
        metrics.record("fast_path", t0)
        if faq_hit and faq_hit.answer:
            outcome.reply = faq_hit.answer
            outcome.intent = "catalog_qa"
            outcome.handled_by = faq_hit.handled_by
            if faq_hit.cacheable:
                await redis_service.set_answer(cache_key, faq_hit.answer)
            await redis_service.add_history(
                str(conversation.id), raw_message, outcome.reply
            )
            return outcome
    elif fast:
        metrics.mark("faq_skipped", f"intent_claimed:{fast.intent}")

    # --- step 8: route, then dispatch ---
    router_degraded = False

    # Mid-flow shortcut: while collecting order details, an incoming message is
    # almost always the answer to the question we just asked. Routing it costs a
    # model call per slot (six per order) for no benefit, so skip the router
    # unless the message looks like the customer changed the subject.
    skip_router = (
        active_flow == "order"
        and state.get("awaiting")
        and not looks_like_topic_change(normalized)
    )

    if skip_router:
        metrics.mark("router_skipped", "mid_flow_slot_answer")
        intent = "order_capture"
        confidence = 1.0
        # Take the deterministic slots even when skipping the router, otherwise
        # "yes" at the confirmation step arrives with no confirm flag and the
        # summary repeats forever.
        slots = fast.slots if (fast and fast.intent == "order_capture") else {}
    elif fast:
        metrics.mark("router_skipped", fast.reason)
        intent = fast.intent
        confidence = fast.confidence
        slots = fast.slots
    elif tenant.is_pro:
        t0 = time.perf_counter()
        decision = await router.route(
            raw_message,
            state=state,
            history=history,
            profile=customer.profile or {},
        )
        metrics.record("router", t0)
        if decision.usage and (
            decision.usage.input_tokens or decision.usage.output_tokens
        ):
            metrics.add_usage(decision.usage.input_tokens, decision.usage.output_tokens)

        if decision.failed:
            # Quota exhausted or unparseable response. Fall back to keyword
            # routing so the customer still gets served — escalating every
            # message because our provider hiccupped is the wrong failure mode.
            router_degraded = True
            intent = heuristic_route(normalized, state)
            confidence = 1.0
            slots = {}
            metrics.mark(
                "router_degraded",
                "rate_limited" if decision.rate_limited else "unparseable",
            )
        else:
            intent = decision.intent
            confidence = decision.confidence
            slots = decision.slots
    else:
        intent = heuristic_route(normalized, state)
        confidence = 1.0
        slots = {}

    # Genuinely ambiguous: try grounded retrieval before giving up. If the
    # tenant's own data has no answer, catalog_qa escalates from there.
    if confidence < LOW_CONFIDENCE_THRESHOLD and active_flow != "order":
        metrics.mark("low_confidence_fallthrough", intent)
        intent = "catalog_qa"

    metrics.mark("intent", intent)
    metrics.mark("confidence", confidence)
    metrics.mark("degraded", router_degraded)
    outcome.intent = intent

    state_update: dict = {}
    profile_update: dict = {}
    escalate_reason: str | None = None
    cacheable = False

    if intent == "human_request":
        outcome.reply = await escalation.raise_escalation(
            db, tenant, conversation, reason="human_request",
            detail=raw_message, customer_wa_id=customer.wa_id,
        )
        outcome.escalated = True
        outcome.handled_by = "human_request"

    elif intent == "order_status":
        result = await order_status.handle(
            db, tenant, customer, raw_message=raw_message, metrics=metrics
        )
        outcome.reply = result.answer
        outcome.handled_by = result.handled_by
        escalate_reason = result.escalate_reason
        if result.input_tokens or result.output_tokens:
            metrics.add_usage(result.input_tokens, result.output_tokens)

    elif intent == "order_capture":
        result = await order_capture.handle(
            db, tenant, customer,
            raw_message=raw_message, normalized=normalized,
            slots=slots, state=state, metrics=metrics,
        )
        outcome.reply = result.answer
        outcome.handled_by = result.handled_by
        state_update = result.state_update
        escalate_reason = result.escalate_reason

    elif intent == "consultation":
        result = await consultation.handle(
            db, tenant, customer,
            raw_message=raw_message, normalized=normalized,
            slots=slots, state=state, metrics=metrics,
        )
        outcome.reply = result.answer
        outcome.handled_by = result.handled_by
        state_update = result.state_update
        profile_update = result.profile_update
        escalate_reason = result.escalate_reason
        if result.input_tokens or result.output_tokens:
            metrics.add_usage(result.input_tokens, result.output_tokens)

    else:  # catalog_qa, payment, other -> grounded Q&A
        result = await catalog_qa.handle(
            db, tenant,
            raw_message=raw_message, normalized=normalized,
            search_query=search_query, history=history, metrics=metrics,
            sales=sales,
        )
        outcome.reply = result.answer
        outcome.handled_by = result.handled_by
        escalate_reason = result.escalate_reason
        cacheable = result.cacheable
        if result.input_tokens or result.output_tokens:
            metrics.add_usage(result.input_tokens, result.output_tokens)

    # Module could not answer -> hand to a human rather than improvise.
    if not outcome.reply and escalate_reason:
        outcome.reply = await escalation.raise_escalation(
            db, tenant, conversation, reason=escalate_reason,
            detail=raw_message, customer_wa_id=customer.wa_id,
        )
        outcome.escalated = True
        outcome.handled_by = f"{outcome.handled_by}_escalated"

    if not outcome.reply:
        outcome.reply = tenant_settings.get(
            "fallback_message",
            "Let me check that and get back to you shortly.",
        )
        outcome.handled_by = outcome.handled_by or "fallback"

    # --- persist conversation state / profile (JSONB needs reassignment) ---
    if state_update:
        conversation.state = {**state, **state_update}
    if profile_update:
        conversation_profile = {**(customer.profile or {}), **profile_update}
        customer.profile = conversation_profile

    # --- cache only factual answers ---
    if cacheable and outcome.reply:
        await redis_service.set_answer(cache_key, outcome.reply)

    # --- usage metering (per tenant, so margin is always known) ---
    if metrics.llm_calls:
        db.add(
            UsageLog(
                tenant_id=tenant.id,
                kind="llm",
                model=None,
                input_tokens=metrics.input_tokens,
                output_tokens=metrics.output_tokens,
                units=metrics.llm_calls,
                meta={"intent": intent, "handled_by": outcome.handled_by},
            )
        )

    await redis_service.add_history(str(conversation.id), raw_message, outcome.reply or "")
    return outcome
