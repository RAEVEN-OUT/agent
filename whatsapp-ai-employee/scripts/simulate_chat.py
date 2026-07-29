"""Local chat simulator — test the whole pipeline with no WhatsApp involved.

This is the fastest way to iterate: it calls the same orchestrator the webhook
calls, so what you see here is exactly what a customer would receive.

Run:
    docker compose exec api python -m scripts.simulate_chat
    docker compose exec api python -m scripts.simulate_chat --plan basic
    docker compose exec api python -m scripts.simulate_chat --script

Type 'quit' to exit, 'reset' to clear the conversation state.
"""

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging import setup_logging
from app.db.models import Conversation, Customer, Tenant
from app.db.session import SessionLocal
from app.pipeline.orchestrator import process_message

TEST_WA_ID = "919999900001"

# A scripted run that exercises every branch of the cascade.
SCRIPT = [
    "hi",
    "how much is the argan oil",
    "what about the 200ml",
    "which shampoo is good for dandruff",
    "oily",
    "dandruff",
    "1000",
    "do you deliver to coimbatore",
    "what are the delivery charges",
    "what are the delivery charges",          # should hit the cache
    "i want to order the tea tree shampoo",
    "2",
    "Aparna",
    "12 Gandhi Street, RS Puram, Coimbatore",
    "641002",
    "cod",
    "where is my order",
    "my scalp is burning after using it",     # must escalate, no auto-answer
]


async def get_context(db, plan: str):
    result = await db.execute(select(Tenant).order_by(Tenant.created_at).limit(1))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise SystemExit("No tenant found. Run:  python -m scripts.seed_demo")

    if tenant.plan != plan:
        tenant.plan = plan
        await db.flush()

    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant.id, Customer.wa_id == TEST_WA_ID)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            tenant_id=tenant.id, wa_id=TEST_WA_ID, name="Simulator", profile={}
        )
        db.add(customer)
        await db.flush()

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant.id,
            Conversation.customer_id == customer.id,
            Conversation.status != "closed",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        conversation = Conversation(tenant_id=tenant.id, customer_id=customer.id, state={})
        db.add(conversation)
        await db.flush()

    return tenant, customer, conversation


async def send(db, tenant, customer, conversation, text: str, verbose: bool) -> None:
    customer.last_inbound_at = datetime.now(timezone.utc)
    outcome = await process_message(
        db, tenant, customer, conversation, raw_message=text
    )
    await db.commit()

    print(f"\n\033[36mCustomer:\033[0m {text}")
    if outcome.silent:
        print("\033[33m[bot silent — human owns this thread]\033[0m")
    else:
        print(f"\033[32mBot:\033[0m {outcome.reply}")

    m = outcome.metrics
    tag = "ESCALATED" if outcome.escalated else (outcome.handled_by or "?")
    cost = f"{m.llm_calls} llm call(s), {m.input_tokens}+{m.output_tokens} tok"
    print(f"\033[90m  [{tag}] intent={outcome.intent} | {cost}\033[0m")
    if verbose:
        print(f"\033[90m  trace={m.trace}\033[0m")
        print(f"\033[90m  timings_ms={m.steps}\033[0m")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", choices=["basic", "pro"], default="pro")
    parser.add_argument("--script", action="store_true", help="run the scripted scenario")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--delay",
        type=float,
        default=13.0,
        help=(
            "seconds between scripted messages. Gemini's free tier allows only "
            "5 requests/minute, so keep this at 13+ on a free key. Set 0.2 once "
            "billing is enabled."
        ),
    )
    args = parser.parse_args()

    setup_logging()

    async with SessionLocal() as db:
        tenant, customer, conversation = await get_context(db, args.plan)
        print(f"\nTenant: {tenant.name}  |  plan={tenant.plan}")
        print("=" * 60)

        if args.script:
            if args.delay >= 5:
                print(
                    f"(pacing {args.delay:.0f}s between messages for free-tier "
                    f"quota — ~{len(SCRIPT) * args.delay / 60:.0f} min total. "
                    "Use --delay 0.2 if billing is enabled.)\n"
                )
            for line in SCRIPT:
                await send(db, tenant, customer, conversation, line, args.verbose)
                await asyncio.sleep(args.delay)
            print("\n" + "=" * 60)
            print(f"conversation state: {conversation.state}")
            print(f"customer profile:   {customer.profile}")
            return

        print("Type a message ('quit' to exit, 'reset' to clear state)\n")
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if text.lower() in ("quit", "exit"):
                break
            if text.lower() == "reset":
                conversation.state = {}
                conversation.human_handoff = False
                conversation.status = "open"
                await db.commit()
                print("state cleared")
                continue
            await send(db, tenant, customer, conversation, text, args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
