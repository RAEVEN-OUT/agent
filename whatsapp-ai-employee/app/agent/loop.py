"""The agent loop: one model conversation per inbound message, with tools.

Replaces hand-written intent routing. The model decides what the customer meant
and which tools to call; the tools enforce every rule that matters. A wrong tool
*sequence* is harmless because the tools refuse invalid states — that is what
makes handing sequencing to a model safe.

What stays deterministic and OUTSIDE this loop (in the orchestrator):
  - safety guardrails (adverse reactions, medical) — policy, not conversation
  - claims scanning on the way out
  - webhook idempotency, rate limiting, state persistence

Multi-domain generalisation comes for free: the tools are identical for a bakery
or a boutique. What changes is the tenant's catalog data and the business
description in the system prompt. No new intent patterns, no new slot logic.
"""

import json
from dataclasses import dataclass, field

from app.agent import business_templates, capabilities
from app.agent import tools as agent_tools
from app.core.config import settings
from app.core.logging import get_logger
from app.pipeline.guardrails import CLAIMS_SYSTEM_RULES, sanitize_outbound
from app.services.llm_service import llm_service

log = get_logger("agent.loop")

try:
    from google.genai import types
except Exception:  # noqa: BLE001  pragma: no cover
    types = None


@dataclass
class AgentResult:
    reply: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    rounds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    escalation_reason: str | None = None
    order_created: str | None = None
    failed: bool = False
    # True when the model asserted a fact without calling any tool this turn.
    ungrounded: bool = False


SYSTEM_TEMPLATE = """You are {bot_name}, the sales assistant for {business} on WhatsApp.
{business_description}

HOW YOU WORK
- You are a salesperson, not a search engine. Answer, then move the sale forward.
- GROUNDING, absolute: never state a fact about a product, price, size, stock,
  ingredient or policy unless you called a tool THIS TURN that returned it.
  Not from memory, not from general knowledge, not "many of our products are...".
  If you are only asking a clarifying question, no tool is needed.
- If a tool returns nothing relevant, say you will check with the team. Do not
  soften a missing fact into a vague claim.
- SEARCH BEFORE ASKING. If the customer names any product, category or type
  ("oil", "shampoo", "what do you sell"), call search_catalog FIRST and show
  what actually exists with names and prices. Only then narrow it down.
  Never reply "yes we have a few options, what are you looking for?" — that is
  an unhelpful claim you did not verify. Show the options, then ask.
- Only ask a clarifying question BEFORE searching when the customer describes a
  problem with no product mentioned at all ("my hair keeps breaking").

WORKING LIKE A SALESPERSON
- If you do not know their name, ask for it once, naturally, at a good moment —
  when taking an order, or after they show real interest. Never as your opening
  line, and never twice.
- Call remember_customer as soon as you learn their name or what they are
  interested in — even if they do not buy. Someone browsing today is a follow-up
  tomorrow, and an unnamed contact cannot be followed up properly.
- Do not tell them you are saving anything. Just do it and carry on.
- Exactly ONE question per message. Never stack two questions.
- Never re-ask something you already know from the context below.
- Keep replies under 60 words. This is WhatsApp, not email.
- No markdown headings. A dash for lists is fine.
- If the customer declines twice, stop pushing and be gracious.
{greeting_rule}

TAKING AN ORDER
- Call save_order_details the moment you learn any detail; it tells you what is
  still missing. Ask for the missing items one at a time.
- If several product variants match, ask which one. Never choose for them.
- Before creating anything, call review_order and read the summary back with the
  total and delivery date, then wait for an explicit yes.
- Only then call place_order. If it returns an error, relay it plainly.

HOW THIS BUSINESS WORKS
{capability_guidance}

TONE
{tone}

{CLAIMS_RULES}

CURRENT CONTEXT
{sales_context}
"""


def _build_tools(allowed: set[str] | None = None):
    """Only declare the tools this tenant's capability kit allows.

    A single-product seller never sees search_catalog; a salon never sees
    place_order. Fewer tools means fewer wrong turns and a smaller prompt.
    """
    if types is None:
        return None
    declarations = []
    for schema in agent_tools.TOOL_SCHEMAS:
        if allowed is not None and schema["name"] not in allowed:
            continue
        try:
            declarations.append(
                types.FunctionDeclaration(
                    name=schema["name"],
                    description=schema["description"],
                    parameters=schema["parameters"],
                )
            )
        except Exception as exc:  # noqa: BLE001
            log.error({"event": "tool_decl_failed", "tool": schema["name"], "error": str(exc)})
    return [types.Tool(function_declarations=declarations)] if declarations else None


def _extract_calls(response) -> list[tuple[str, dict]]:
    calls = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            fn = getattr(part, "function_call", None)
            if fn is not None and getattr(fn, "name", None):
                args = getattr(fn, "args", None) or {}
                calls.append((fn.name, dict(args)))
    return calls


def _text_of(response) -> str:
    chunks = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text and not getattr(part, "thought", False):
                chunks.append(text)
    return "".join(chunks).strip()


async def run(
    *,
    db,
    tenant,
    customer,
    conversation,
    message: str,
    history: list[dict],
    sales,
    metrics,
) -> AgentResult:
    result = AgentResult()

    if not llm_service.available or types is None:
        result.failed = True
        return result

    tenant_settings = tenant.settings or {}
    system_prompt = SYSTEM_TEMPLATE.format(
        bot_name=tenant_settings.get("bot_name", "the assistant"),
        business=tenant_settings.get("business_name", tenant.name),
        business_description=tenant_settings.get("business_description", ""),
        tone=tenant_settings.get("tone", "warm, friendly, concise"),
        capability_guidance="\n".join(
            part for part in (
                business_templates.for_tenant(tenant).extra_prompt,
                capabilities.prompt_additions(tenant),
                f"WHAT SUCCESS LOOKS LIKE: {business_templates.for_tenant(tenant).goal}",
            ) if part
        ),
        CLAIMS_RULES=CLAIMS_SYSTEM_RULES,
        sales_context=sales.as_prompt_block() if sales else "",
        # Greeting every message by name reads like a mail-merge, not a person.
        greeting_rule=(
            (
                "- This is their first message: greet them once, warmly."
                if not history
                else "- You are MID-CONVERSATION. Do NOT greet again."
            )
            + "\n"
            + (
                "- NEVER open a reply with 'Hi <name>' or 'Hello <name>'. That "
                "formula reads like a mail merge and is the fastest way to look "
                "automated.\n"
                "- Use their name RARELY — at most once in a few messages, mid "
                "sentence, where it adds warmth ('that one's very popular, "
                "Raveen'). Most replies should use no name at all.\n"
                "- Vary your openings. Do not start consecutive replies the same way."
            )
        ),
    )

    ctx = agent_tools.ToolContext(
        db=db, tenant=tenant, customer=customer,
        conversation=conversation, metrics=metrics,
    )

    contents = []
    for turn in (history or [])[-4:]:
        if turn.get("user"):
            contents.append(
                types.Content(role="user", parts=[types.Part(text=turn["user"])])
            )
        if turn.get("bot"):
            contents.append(
                types.Content(role="model", parts=[types.Part(text=turn["bot"])])
            )
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    allowed = capabilities.allowed_tools(tenant)
    tool_config = _build_tools(allowed)
    metrics.mark("capabilities", sorted(allowed))

    for round_index in range(settings.AGENT_MAX_ROUNDS):
        result.rounds = round_index + 1
        try:
            response = await llm_service.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                    tools=tool_config,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            log.error({"event": "agent_call_failed", "round": round_index, "error": str(exc)[:300]})
            result.failed = True
            return result

        usage = getattr(response, "usage_metadata", None)
        if usage:
            result.input_tokens += getattr(usage, "prompt_token_count", 0) or 0
            result.output_tokens += getattr(usage, "candidates_token_count", 0) or 0

        calls = _extract_calls(response)
        if not calls:
            text = _text_of(response)
            safe, violations = sanitize_outbound(text)
            if violations:
                log.warning({"event": "claim_blocked", "where": "agent"})
            result.reply = safe or None
            result.escalation_reason = ctx.escalation_reason
            result.order_created = ctx.order_created

            # Grounding watchdog. If the model asserted something without calling
            # any tool this turn, that claim came from its own knowledge — the one
            # failure mode grounding is supposed to prevent. A pure clarifying
            # question is legitimate; an assertion is not.
            if result.reply and not result.tool_calls:
                # A pure clarifying question needs no tool. An existence or
                # numeric claim does. Length is a poor proxy — look for the
                # claim itself.
                lowered = result.reply.lower()
                asserts_fact = any(char.isdigit() for char in result.reply) or any(
                    phrase in lowered
                    for phrase in (
                        "we have", "we offer", "we stock", "we sell", "we carry",
                        "all our", "our products are", "our range", "we specialize",
                        "we specialise", "is available", "are available", "in stock",
                    )
                )
                if asserts_fact:
                    result.ungrounded = True
                    log.warning(
                        {
                            "event": "ungrounded_reply",
                            "reply": result.reply[:200],
                            "hint": "asserted a fact with no tool call this turn",
                        }
                    )

            if not result.reply:
                result.failed = True
            return result

        # Append the model's ACTUAL content object, never a reconstruction.
        #
        # Gemini 3.x attaches a `thought_signature` to each functionCall part and
        # requires it echoed back on the next turn. Rebuilding the part with
        # types.FunctionCall(name=..., args=...) drops it, and the API rejects the
        # follow-up with:
        #   400 "Function call is missing a thought_signature in functionCall parts"
        # Passing the original candidate content preserves the signature and any
        # future fields the SDK adds.
        model_content = None
        for candidate in getattr(response, "candidates", None) or []:
            if getattr(candidate, "content", None) is not None:
                model_content = candidate.content
                break
        if model_content is None:  # nothing to echo back; bail rather than loop
            log.error({"event": "agent_no_candidate_content"})
            result.failed = True
            return result
        contents.append(model_content)
        response_parts = []
        for name, args in calls:
            result.tool_calls.append(name)
            output = await agent_tools.execute(name, args, ctx)
            log.info(
                {
                    "event": "tool_call",
                    "tool": name,
                    "args": json.dumps(args, default=str)[:200],
                    "ok": "error" not in output,
                }
            )
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name, response={"result": output}
                    )
                )
            )
        contents.append(types.Content(role="user", parts=response_parts))

    # Ran out of rounds without producing a reply.
    log.warning({"event": "agent_max_rounds", "calls": result.tool_calls})
    result.failed = True
    result.escalation_reason = ctx.escalation_reason or "cannot_answer"
    result.order_created = ctx.order_created
    return result
