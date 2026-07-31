# Answer — 30 July 2026 (sixth update)

## Headline: agent mode works. It has never worked before this run.

Read your own output again, ignoring the PASS/FAIL column:

```
tool_call search_catalog {"query": "argan oil"}   ok: true
"Our Argan Repair Hair Oil comes in two sizes: 100ml for INR 449 and
 200ml for INR 799. Which size would you like to go for?"
```

That is the ₹898 bug fixed — it **asked which size instead of silently picking
one**. And this:

```
tool_call search_catalog {"query": "silk finish serum"}   ok: true
"The Silk Finish Hair Serum is priced at INR 399 for 50ml, but it is
 currently out of stock. Would you like me to notify you when it's back?"
```

Correct price, correct stock, sensible next step. Every guardrail passed. No
crashes. The `thought_signature` and `NoneType` fixes landed.

**18 of your 22 "failures" were the test harness measuring the architecture we
deleted.** Two were real. Details below.

---

## 1. Why a working bot scored 9/27

Two assertions in the harness became meaningless in agent mode:

**`intent=agent expected=catalog_qa`** — in agent mode there is no intent
classification. The model picks tools; `outcome.intent` is always `"agent"`. The
golden set was asserting the labels of the classifier we removed.

**`cost 1 llm call(s), expected free`** — those cases were marked `free` because
the old keyword fast path answered them with zero model calls. In agent mode they
cost one call. **That is the trade we deliberately made** — $0.10/month per client
for accuracy. The harness was reporting the intended design as a defect.

### Fixed: the harness now asserts behaviour, not internals

In agent mode it checks:

| assertion | why |
|---|---|
| **which tools ran** (`expect_tools`) | the meaningful routing check now |
| **facts present** (`must_contain`) | did it quote the real price / policy |
| **forbidden claims absent** (`must_not`) | compliance |
| **escalation correctness** | safety |
| **ungrounded replies** | asserted facts with no tool call — see below |

Legacy `expect_intent` / `expect_route` still apply when `AGENT_MODE=false`, so you
can still A/B the two architectures on the same file.

Golden set is now **31 cases, 21 with tool expectations**, including four real
messages from your live WhatsApp session that the old build failed:

- `"u got argan oil"` → must quote 449
- `"i want to order ur oil"` → must mention **both** 100 and 200 (must ask, not pick)
- `"u have shampoo"` → must **not** answer with the sulphate FAQ
- `"wht products do u sell"` → must call `search_catalog`

---

## 2. Real bug: an ungrounded answer

```
FAIL  sulphate_free   1 llm   1125ms          <- no tool_call line above it
"Yes, many of our products are sulphate-free."
```

No tool was called. The model answered **from its own knowledge**, and hedged with
"many" — while your actual FAQ says every shampoo is sulphate-free and the whole
range is paraben-free. So it was both ungrounded *and* less accurate than the
truth sitting in the database.

This is the one failure mode grounding exists to prevent, so it now has three
layers:

1. **Sharper prompt rule** — never state a fact about a product, price, stock,
   ingredient or policy unless a tool returned it *this turn*. Explicitly bans the
   "many of our products are…" hedge. Clarifying questions still need no tool.
2. **Runtime watchdog** — if the reply asserts something and no tool ran, it logs
   `ungrounded_reply` with the text. Visible instead of silent.
3. **Eval assertion** — any case with `expect_tools` fails loudly if nothing ran.

I checked the whole run for this pattern: only two cases had no tool call.
`sulphate_free` (a real violation) and `advisory_open_ended`, which asked "is your
hair naturally dry, or is it damage?" — a clarifying question, correctly needing
no tool. So the watchdog distinguishes the two rather than flagging both.

---

## 3. Real issue: it greeted on every single message

Every reply opened with "Hi Eval!". In the eval that is technically fine — each
case runs in a fresh conversation, so each *is* a first message. In a real chat it
would read like a mail merge.

Fixed: the prompt now depends on history. First message → greet once. Otherwise →
explicitly told it is mid-conversation, do not greet, do not open with their name.
There is also a `forbid_greeting` assertion available for golden cases.

---

## 4. Worth noticing about quality

Things the bot did that no rule told it to:

- `"how much for the 200ml argan oil"` → answered **only** about the 200ml (₹799),
  correctly not listing both, because the size was specified
- `"where is my order"` → no orders found, so it offered to place one instead of
  dead-ending
- `"my hair keeps breaking"` → asked a qualifying question before recommending
- Out-of-stock item → offered a back-in-stock notification

That is the salesperson behaviour you asked for, and none of it is hand-written.
It is what the old architecture could not do without a code change per case.

**Latency: 1.1–3.9s per reply.** Fine for WhatsApp.

---

## Changes

| file | change |
|---|---|
| `app/agent/loop.py` | grounding rule + watchdog; greeting depends on history |
| `scripts/eval_harness.py` | behaviour-based assertions in agent mode; `expect_tools` |
| `tests/golden_set.json` | 27 → 31 cases; 21 with tool expectations; 4 from your live session |

218 unit tests passing.

---

## What to run

```bash
git pull
docker compose up -d --build
docker compose exec api python -m scripts.eval_harness --delay 13 --verbose
```

Expect a much higher score, because it is finally measuring the right thing. What
to look for:

- Any `UNGROUNDED` failure → the model answered without retrieving. Report it.
- Any `did not call <tool>` → routing genuinely went wrong.
- `ambiguous_variant` must mention **both** 100 and 200.
- No reply should start with "Hi" except the first message of a conversation.

Then a live WhatsApp conversation, COD only, end to end: browse → ask a policy
question → order → confirm → ask about the order afterwards.

## Next, in order

1. **Multi-tenant test** — two tenants, different kits, confirm nothing leaks.
   Never tested, and it is the core promise of the platform.
2. **Alembic migrations** — the first schema change after a client has real orders
   currently destroys their data.
3. **Admin panel** — a seller cannot run `seed_demo`. Without it you have a demo
   you operate, not a product they use.
4. Backups, monitoring, restart policy on `api`.
5. Then payments.

**Commit and push from Windows — nothing here reaches your main laptop until you do.**
