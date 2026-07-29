"""Accuracy + cost evaluation against the golden set.

This is the answer to "can we always be accurate?" — you cannot guarantee it,
but you can measure it, so optimisation stops being guesswork. Run this before
and after any change to thresholds, prompts, or models.

    docker compose exec api python -m scripts.eval_harness
    docker compose exec api python -m scripts.eval_harness --plan basic
    docker compose exec api python -m scripts.eval_harness --delay 13   # free tier
    docker compose exec api python -m scripts.eval_harness --only advisory

Each case runs in a fresh conversation so state cannot leak between them.
Reports per-case pass/fail plus the two numbers that matter:
  - free-path rate  (how many messages cost nothing)
  - accuracy        (how many replies contained the required facts)
"""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.models import Conversation, Customer, Tenant
from app.db.session import SessionLocal
from app.pipeline.orchestrator import process_message

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "tests" / "golden_set.json"
EVAL_WA_ID = "919999900099"

GREEN, RED, YELLOW, GREY, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


@dataclass
class CaseResult:
    case_id: str
    message: str
    reply: str
    intent: str | None
    llm_calls: int
    in_tokens: int
    out_tokens: int
    escalated: bool
    latency_ms: float
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate(case: dict, outcome, latency_ms: float) -> CaseResult:
    reply = (outcome.reply or "").lower()
    failures: list[str] = []

    expected_intent = case.get("expect_intent")
    if expected_intent and outcome.intent != expected_intent:
        failures.append(f"intent={outcome.intent} expected={expected_intent}")

    route = case.get("expect_route", "either")
    if route == "free" and outcome.metrics.llm_calls > 0:
        failures.append(f"cost {outcome.metrics.llm_calls} llm call(s), expected free")
    if route == "llm" and outcome.metrics.llm_calls == 0:
        failures.append("answered without an llm call — likely a canned answer to a judgement question")

    for needle in case.get("must_contain", []):
        if needle.lower() not in reply:
            failures.append(f"missing {needle!r}")

    for needle in case.get("must_not", []):
        if needle.lower() in reply:
            failures.append(f"FORBIDDEN {needle!r} present")

    if case.get("expect_escalate") and not outcome.escalated:
        failures.append("should have escalated to a human")
    if not case.get("expect_escalate") and outcome.escalated:
        failures.append("escalated unnecessarily")

    return CaseResult(
        case_id=case["id"],
        message=case["message"],
        reply=outcome.reply or "",
        intent=outcome.intent,
        llm_calls=outcome.metrics.llm_calls,
        in_tokens=outcome.metrics.input_tokens,
        out_tokens=outcome.metrics.output_tokens,
        escalated=outcome.escalated,
        latency_ms=latency_ms,
        failures=failures,
    )


async def fresh_conversation(db, tenant, customer) -> Conversation:
    """Each case gets a clean conversation so prior state cannot leak in."""
    await db.execute(
        delete(Conversation).where(
            Conversation.tenant_id == tenant.id, Conversation.customer_id == customer.id
        )
    )
    conversation = Conversation(tenant_id=tenant.id, customer_id=customer.id, state={})
    db.add(conversation)
    await db.flush()
    return conversation


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", choices=["basic", "pro"], default="pro")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds between cases (use 13 on a free Gemini key)")
    parser.add_argument("--only", default=None, help="substring filter on case id")
    parser.add_argument("--verbose", action="store_true", help="print every reply")
    args = parser.parse_args()

    setup_logging()
    import logging

    if not args.verbose:  # keep the report readable
        logging.getLogger().setLevel("ERROR")

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = golden["cases"]
    if args.only:
        cases = [c for c in cases if args.only in c["id"]]

    results: list[CaseResult] = []

    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).order_by(Tenant.created_at).limit(1))
        ).scalar_one_or_none()
        if not tenant:
            raise SystemExit("No tenant. Run: python -m scripts.seed_demo")
        if tenant.plan != args.plan:
            tenant.plan = args.plan
            await db.flush()

        customer = (
            await db.execute(
                select(Customer).where(
                    Customer.tenant_id == tenant.id, Customer.wa_id == EVAL_WA_ID
                )
            )
        ).scalar_one_or_none()
        if not customer:
            customer = Customer(
                tenant_id=tenant.id, wa_id=EVAL_WA_ID, name="Eval", profile={}
            )
            db.add(customer)
            await db.flush()

        print(f"\nmodel={settings.GEMINI_MODEL}  router={settings.GEMINI_ROUTER_MODEL}")
        print(f"plan={tenant.plan}  fts_threshold={settings.FTS_FAST_PATH_RANK}")
        print(f"cases={len(cases)}\n")

        for case in cases:
            # Reset per-case memory so a cached answer from an earlier case does
            # not make a later one look free.
            customer.profile = {}
            conversation = await fresh_conversation(db, tenant, customer)

            t0 = time.perf_counter()
            outcome = await process_message(
                db, tenant, customer, conversation, raw_message=case["message"]
            )
            latency = (time.perf_counter() - t0) * 1000
            await db.commit()

            result = evaluate(case, outcome, latency)
            results.append(result)

            mark = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
            cost = "free" if result.llm_calls == 0 else f"{result.llm_calls} llm"
            print(f"{mark}  {result.case_id:<28} {GREY}{cost:>7} {latency:>6.0f}ms{RESET}")
            if not result.passed:
                for failure in result.failures:
                    print(f"      {RED}- {failure}{RESET}")
                print(f"      {GREY}reply: {result.reply[:160]}{RESET}")
            elif args.verbose:
                print(f"      {GREY}{result.reply[:160]}{RESET}")

            if args.delay:
                await asyncio.sleep(args.delay)

    # ---------------- report ----------------
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    free = sum(1 for r in results if r.llm_calls == 0)
    tokens_in = sum(r.in_tokens for r in results)
    tokens_out = sum(r.out_tokens for r in results)
    calls = sum(r.llm_calls for r in results)
    avg_latency = sum(r.latency_ms for r in results) / max(total, 1)

    print("\n" + "=" * 62)
    print(f"accuracy        {passed}/{total}  ({passed / max(total,1) * 100:.0f}%)")
    print(f"free path       {free}/{total}  ({free / max(total,1) * 100:.0f}% cost nothing)")
    print(f"llm calls       {calls}")
    print(f"tokens          {tokens_in} in / {tokens_out} out")
    print(f"avg latency     {avg_latency:.0f} ms")

    # Cost per 1000 conversations, assuming ~10 messages each.
    prices = {
        "gemini-2.5-flash-lite": (0.10, 0.40),
        "gemini-3.1-flash-lite": (0.25, 1.50),
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-3.6-flash": (1.50, 7.50),
    }
    rate = prices.get(settings.GEMINI_MODEL)
    if rate and total:
        per_msg = (tokens_in / total / 1e6 * rate[0]) + (tokens_out / total / 1e6 * rate[1])
        print(
            f"\ncost/message    ${per_msg:.6f}"
            f"   -> ${per_msg * 10 * 300:.2f}/month at 300 conversations"
        )

    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\n{RED}{len(failures)} failing case(s):{RESET}")
        for r in failures:
            print(f"  {r.case_id}: {'; '.join(r.failures)}")
        print(
            f"\n{YELLOW}Tip: 'cost N llm calls, expected free' usually means "
            f"FTS_FAST_PATH_RANK is too high — run scripts.tune_retrieval.{RESET}"
        )
    else:
        print(f"\n{GREEN}all cases passed{RESET}")
    print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())
