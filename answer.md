# Answer — 30 July 2026

Covers two things: (1) verifying Gemini's analysis in `question.md`, and (2) how
the bot correctly asked for a pincode after your address with zero AI calls.

---

## Part 1 — Verifying Gemini's analysis

**Verdict: partly right, one wrong cause, and it missed the biggest bug.**

### ✅ Correct: Qdrant `.search` → `.query_points`

Right diagnosis. The client library renamed the method, so vector search threw
`'AsyncQdrantClient' object has no attribute 'search'` on every call. Fixed in
`qdrant_service.py`, which now supports both method names so a future client
upgrade cannot silently disable retrieval again.

### ❌ WRONG: the cause of the "yes" confirmation loop

Gemini said:

> "Your earlier test run occurred before the container was re-created with the
> updated `fast_intent.py` confirmation slot logic."

That is not what happened, and believing it means the bug comes back.

**Proof from your own log** — the "yes" message traced:

```json
"trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", ...}
```

That `router_skipped: mid_flow_slot_answer` marker **only exists in the new
code**. The container was running the updated build. `fast_intent.py` did have
the confirm logic — it was simply never consulted.

**The real cause** was an ordering bug in `orchestrator.py`. The mid-flow
shortcut ran *before* the deterministic confirm parser:

```python
skip_router = active_flow == "order" and state.get("awaiting") and not topic_change
if skip_router:
    intent = "order_capture"
    slots = {}          # <-- confirm flag thrown away here
elif fast:
    slots = fast.slots  # <-- never reached mid-flow
```

So `slots.get("confirm")` was always `None`, and `order_capture` re-printed the
summary forever. Fixed by taking the deterministic slots even when the router is
skipped, plus a stuck-counter: an unrecognised reply now gets "Reply YES to
confirm or NO to cancel", and after three attempts it hands off to a human.
("get outtt" should never have hit the same wall three times.)

### ❌ MISSED: the biggest bug — Postgres AND-semantics

Gemini blamed the failed product questions entirely on Qdrant. But your log shows
keyword search failing **independently**:

```json
"trace": {"fts_faq_rank": 0.0, "fts_products": 0, "semantic_chunks": 0,
          "path": "no_grounding"}
```

`fts_products: 0` means **Postgres full-text search found no products for
"how much is argan oil"** — nothing to do with Qdrant.

Cause: `plainto_tsquery` **ANDs every term**. The query became:

```
much & argan & oil
```

No product contains the word "much", so it matched nothing. Every message
padded with ordinary conversational filler failed the same way:

| message | old query (AND) | result |
|---|---|---|
| how much is argan oil | `much & argan & oil` | 0 products |
| wht products do u sell | `products & sell` | 0 products |
| is ur shampoo sulfate free | `shampoo & sulfate & free` | 0 products |

Fixed by OR-ing the meaningful terms and letting `ts_rank` discriminate — a
document matching more terms ranks higher, and the threshold filters the rest:

| message | new query (OR) |
|---|---|
| how much is argan oil | `argan \| oil` |
| wht products do u sell | `products \| sell` |
| is ur shampoo sulfate free | `shampoo \| sulphate \| free` |

**Why this matters:** if you had only applied Gemini's Qdrant fix, keyword search
would still be broken. Every product question would fall through to embeddings +
vector search — slower, costlier, and the whole zero-cost fast path would be
dead. It would have looked "fixed" while quietly costing money on every message.

### ❌ MISSED: it sold a variant the customer never chose

From your transcript:

```
Raveen: I want to order ur oil
Bot:    How many would you like?
...
Bot:    2 x Argan Repair Hair Oil
        Total: INR 898
```

"oil" matched **both** the 100ml (₹449) and 200ml (₹799) Argan Oil. It silently
took the first and billed ₹898. In production that ships the wrong size and
becomes a refund. It now asks which variant, and the size appears in the summary
and on the order record.

### ❌ MISSED: sulfate vs sulphate

Your catalog says "sulphate" (British); customers type "sulfate" (American). They
never matched. US/UK spelling variants are now normalised before search.

### ⚠️ Partly right: Phase 2 "Live Agent Handover"

The pause-the-bot half **already exists**. `conversation.human_handoff` is set on
escalation, and the orchestrator returns silent when it is true, so the bot will
not talk over a human. What is genuinely missing is the agent-facing side: a UI
to see escalations and reply, and a notification when one is raised.

### Correct: keep the hybrid architecture

Gemini's conclusion here is right, and your log is the evidence. The paths that
worked, worked because retrieval worked. The paths that failed, failed because
**the data was never found** — an LLM handed nothing to ground on either says
"let me check with our team" (what happened) or invents a price. Routing
everything through the model would have multiplied cost and hidden a database
bug behind plausible sentences.

Your order flow ran at **0 LLM calls** end to end, with sub-millisecond routing.

---

## Part 2 — How it asked for the pincode with no AI

Short answer: **it never understood your address.** It filed whatever you typed
into the slot it was waiting on, then asked for the next empty slot.

`order_capture.py` holds a fixed list:

```python
REQUIRED_SLOTS = ("product", "quantity", "name", "address", "pincode", "payment_method")
```

The loop is:

1. Find the first empty slot → ask its question → record `awaiting = "address"`.
2. Next message arrives → `draft["address"] = raw_message` (no interpretation).
3. Find the next empty slot → `pincode` → ask for it.

Your log shows exactly this, with no model call:

```json
{"path": "order_ask_address",  "llm_calls": 0}
{"path": "order_ask_pincode",  "llm_calls": 0}
```

So the intelligence you saw was **sequencing, not comprehension**. The bot did
not recognise "no 2 tamilan nagar kavangarai" as an address — it would have
accepted anything. If you had typed "banana" at that step, your delivery address
would now be "banana".

### Where validation does exist

Only where it was written explicitly:

| slot | validation |
|---|---|
| quantity | integer 1–50, else re-ask |
| pincode | exactly 6 digits, else re-ask |
| payment_method | keyword match (cod / cash / upi / card / online) |
| product | must resolve against the real catalog; ambiguity → ask |
| **address** | **none — accepts any text** |
| **name** | **none — accepts any text** |

### Known gap

Address and name are unvalidated free text. A customer replying "yes" at the
address step gets "yes" as their delivery address. Two ways to close it:

- **WhatsApp Flows** (Phase 2) — a native in-chat form with proper fields. Best
  UX and validates before submission.
- A lightweight sanity check — minimum length, must contain a digit or a comma,
  reject single-word answers.

This is the honest trade of the deterministic design: perfectly reliable
sequencing, zero understanding. Where understanding is actually needed (advice,
comparisons, open-ended questions) the LLM is used — which is why "do u have
shampoo for dandruff" cost 2 LLM calls and produced a genuinely good answer,
while the entire order flow cost nothing.

---

## Changes in this update

| file | change |
|---|---|
| `app/modules/retrieval.py` | OR-based tsquery (`build_or_tsquery`) replacing AND semantics |
| `app/services/qdrant_service.py` | `query_points()` with `search()` fallback |
| `app/pipeline/orchestrator.py` | keep deterministic slots when the router is skipped |
| `app/modules/order_capture.py` | variant disambiguation, size carried through, confirm stuck-counter |
| `app/pipeline/normalize.py` | US/UK spelling variants (sulfate → sulphate, etc.) |
| `tests/test_search_query.py` | new — regression tests for the AND-semantics bug |
| `CLAUDE.md` | standing instruction for the question.md / answer.md workflow |

139 tests passing.

---

## What to run next

```bash
git pull
docker compose up -d --build
docker compose exec api python -m scripts.tune_retrieval
docker compose exec api python -m scripts.eval_harness --delay 13
```

`tune_retrieval` matters this time — rank values change under OR semantics, so
`FTS_FAST_PATH_RANK` needs recalibrating. No re-seed required; the query change
takes effect immediately.

Then re-test the order flow on WhatsApp, specifically:

1. "how much is argan oil" → should quote ₹449 (was failing)
2. "is ur shampoo sulfate free" → should answer from the FAQ (was failing)
3. "I want to order ur oil" → should ask **which size** (was silently picking one)
4. Complete an order and reply "yes" → should confirm, not loop

## Suggested next phase

Before building new features, add the real messages from your transcript to
`tests/golden_set.json` — they found four bugs my invented cases missed. Then
Phase 2 in this order:

1. **Razorpay payment links** — test keys are already in `.env`
2. **WhatsApp cart/`order` messages** → straight into an Order
3. **Next.js admin panel** — escalation inbox, order management, usage/cost per tenant
