# AI Employee Platform — Phase 1

Multi-tenant WhatsApp automation for SMEs. Pilot tenant: a hair care seller.

One codebase, many tenants. Client-specific behaviour comes from tenant config
and uploaded data, never from a forked copy of the code.

**Status:** Phase 1 complete and runnable. 65 unit tests passing. Webhook
security, cost cascade, routing, catalog Q&A, consultation, order capture,
order status and escalation all working end to end.

---

## Quickstart

Everything runs in Docker. From this directory:

```bash
# 1. bring up api + postgres + redis + qdrant
docker compose up --build

# 2. in a second terminal: confirm credentials and infra actually work
docker compose exec api python -m scripts.verify_credentials

# 3. seed the pilot tenant (products, FAQs, vector index)
docker compose exec api python -m scripts.seed_demo

# 4. talk to the bot with no WhatsApp involved
docker compose exec api python -m scripts.simulate_chat
```

`simulate_chat` calls the same orchestrator the webhook calls, so what you see
is exactly what a customer would get. Useful flags:

```bash
# run a scripted scenario that exercises every branch
docker compose exec api python -m scripts.simulate_chat --script

# see the same conversation on the Basic plan (no LLM router)
docker compose exec api python -m scripts.simulate_chat --plan basic --script

# show per-step timings and the decision trace
docker compose exec api python -m scripts.simulate_chat --verbose
```

### Connecting real WhatsApp

The webhook needs a public HTTPS URL. Locally:

```bash
ngrok http 8000
```

Then in the Meta App Dashboard → **WhatsApp → Configuration → Webhook**:

- **Callback URL:** `https://<your-ngrok-subdomain>.ngrok-free.app/webhook`
- **Verify token:** the same string as `WHATSAPP_VERIFY_TOKEN` in `.env`
- **Subscribe to:** the `messages` field

Message the test business number from your own phone (the number you added as a
test recipient). Watch the logs — each message prints which cascade step
answered and how many tokens it cost.

---

## Tests

```bash
docker compose exec api python -m pytest -q
# or locally, no containers needed:
pip install -r requirements.txt && python -m pytest -q
```

The guardrail tests are the important ones. A false negative there means either
an unanswered adverse reaction or a claim that can get the client's WhatsApp
number banned.

---

## Cost & accuracy tooling

```bash
# measure accuracy + free-path rate against the golden set
docker compose exec api python -m scripts.eval_harness
docker compose exec api python -m scripts.eval_harness --plan basic
docker compose exec api python -m scripts.eval_harness --delay 13   # free Gemini key

# calibrate the fast-path threshold (no LLM calls)
docker compose exec api python -m scripts.tune_retrieval
docker compose exec api python -m scripts.tune_retrieval --semantic
```

Run `eval_harness` before and after any change to a threshold, prompt, or model.
It prints accuracy, what fraction of messages cost nothing, and the projected
monthly cost. `tests/golden_set.json` is where every message the bot gets wrong
in the real world should be added — that file is the only thing standing between
"optimised" and "quietly degraded".

## Zero-AI entry points (the highest-converting path)

A customer who taps a product button, scans a QR on the packaging, or clicks an
ad already told you what they want. Encode the SKU in the link:

```
https://wa.me/<number>?text=PRODUCT%3A%20ARG-OIL-100
https://wa.me/<number>?text=%23ROSE-SHM-200
```

`fast_intent` reads that on the first message and jumps straight into order
capture — no routing, no inference, no model call. Messages arriving from an ad
that clicks to WhatsApp carry a `referral` payload, which `_entry_context` in
`webhook.py` parses for the same purpose.

From there the whole flow is deterministic: collect details → summary with total
and delivery date → confirm → order created. A single-product seller can run
end-to-end with **zero LLM calls**.

## How a message flows

```
inbound webhook
  ├─ verify X-Hub-Signature-256          reject if not from Meta
  ├─ dedupe by wamid (Redis SETNX)       Meta retries for 7 days
  ├─ resolve tenant by phone_number_id
  ├─ rate limit per customer
  └─ orchestrator cascade:
       1. normalize + gibberish filter        zero cost
       2. safety guardrails                   zero cost   -> escalate
       3. small talk (canned)                 zero cost
       4. answer cache (facts only)           zero cost
       5. local follow-up rewrite             zero cost
       6. keyword FAQ fast path (Postgres FTS) ~ms, no API call
       7. deterministic intent gate            zero cost  <- fast_intent
       8. embeddings + Qdrant                  cheap, cached 7d
       9. LLM route + compose                  last resort
```

Returns at the first step that can answer confidently. On the golden set, 63% of
messages are resolved before the LLM router is even consulted — higher in
practice, since that measurement excludes the DB-backed FAQ fast path.

Step 7 (`fast_intent`) is a **confidence gate**, not a replacement router. Its
contract is high precision, low recall: returning `None` is free because the LLM
router picks it up, but a confident wrong answer sends the customer down the
wrong flow. Anything advisory is refused outright.

### The tier rule

When nothing is confident: **Basic hands off to the human, Pro hands off to the
LLM.** That single rule defines both plans. Switch with `tenant.plan`.

### Two design rules worth not breaking

**Cache facts, not conversations.** Retrieval (price, stock, policy) is cached.
Composed sales replies never are — that is where the selling happens. Advisory
questions ("which is better for dry hair") are explicitly blocked from every
fast path, no matter how well they keyword-match.

**Conversation order is free; transaction order is not.** The AI may raise
add-ons before, after, or instead of closing. It cannot create an order without
stock, an address, or a payment method — those preconditions live in
`order_capture`, not in the prompt.

---

## Layout

```
app/
  core/        config, structured logging, retry, per-message metrics
  db/          SQLAlchemy models (tenant-scoped), async session
  services/    redis, gemini, qdrant, whatsapp, event bus
  pipeline/    normalize, smalltalk, guardrails, router, orchestrator
  modules/     retrieval, catalog_qa, consultation, order_capture,
               order_status, escalation
  api/         webhook (GET verify + POST receive), health
scripts/       verify_credentials, seed_demo, simulate_chat
tests/         65 unit tests, no network or DB required
```

### Adding a per-client integration without touching core code

The backend emits domain events (`order.created`, `payment.received`,
`escalation.raised`, ...). A "log orders to my Google Sheet" request becomes a
subscriber, not a fork:

```python
from app.services.events import ORDER_CREATED, event_bus

async def push_to_sheet(event: str, payload: dict) -> None:
    ...

event_bus.subscribe(ORDER_CREATED, push_to_sheet)
```

`event_bus.add_outbound_webhook(url)` exposes the same stream over HTTP, so n8n
or any external tool can consume it later without a rewrite.

---

## Compliance built in (hair care vertical)

WhatsApp's Business Messaging Policy prohibits messaging about medical and
healthcare products. Cosmetic hair care is fine; therapeutic claims are not.

- `guardrails.check_inbound` — adverse reactions, medical questions and
  complaints never get an automated reply. They escalate to a human and lock
  the thread (`conversation.human_handoff`), so the bot stays silent afterwards.
- `guardrails.scan_outbound` — blocks "cures", "regrows", "guaranteed",
  "no side effects", pregnancy-safety claims and similar in any generated reply,
  regardless of what the model produced.
- The model is also told the rules (`CLAIMS_SYSTEM_RULES`), but the regex is what
  enforces them. A prompt can be talked out of its instructions; a regex cannot.
- Escalation paths exist because policy requires them when you automate replies
  inside the 24-hour window.

Grounding: every reply is composed only from that tenant's retrieved data. If
retrieval returns nothing relevant, the bot escalates instead of answering from
general knowledge.

---

## Known gaps (by design, next phases)

- **Payments** — `order_capture` records the method and total but does not yet
  create a Razorpay link (Phase 2).
- **Follow-ups / replenishment / campaigns** — the schedulers are not built yet;
  they need `arq` workers and approved WhatsApp templates (Phase 3).
- **Admin panel** — no Next.js UI yet; catalog changes go through
  `scripts/seed_demo.py` (Phase 3).
- **Migrations** — `AUTO_CREATE_TABLES=true` uses `create_all`. Move to Alembic
  before there is tenant data you cannot rebuild.
- **Dual-store consistency** — Postgres and Qdrant share no transaction. Catalog
  writes must update both; a reconciliation job is still to be written.
- **Cart messages** — WhatsApp `order` type webhooks are parsed but not yet
  converted straight into an `Order` (Phase 2).

---

## Operational notes

- **The token Meta shows first expires in ~24h.** Use a System User token
  (see `credentials-setup-checklist.md`, section 1f) or the bot dies overnight.
- **Pin the API version.** `WHATSAPP_API_VERSION` is one config value. Meta
  supports each version for roughly two years; bumping it is a five-minute
  change plus a changelog read.
- **Watch the quality rating.** `verify_credentials` prints it. A falling rating
  shrinks your messaging limits before it bans anything.
- **Every message logs its cost.** Grep the logs for `llm_calls` and
  `input_tokens` to see cascade effectiveness per tenant.
