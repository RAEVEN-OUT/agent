# Answer — 30 July 2026 (fifth update)

Your `question.md` was the traceback from running agent mode live. Two real bugs,
both fixed. Then the strategic question: can one project serve single-product
sellers, inventory search, need-based filtering, and appointment booking — or do
you sell per-client automation?

**218 tests passing.**

---

## Part 1 — The two bugs from your live run

### Bug 1: `thought_signature` — Gemini 3 requirement I got wrong

```
400 INVALID_ARGUMENT: Function call is missing a thought_signature in
functionCall parts. This is required for tools to work correctly.
```

**Cause:** after the model requested a tool, I rebuilt its turn by hand:

```python
types.Part(function_call=types.FunctionCall(name=name, args=args))   # WRONG
```

Gemini 3.x attaches a `thought_signature` to each `functionCall` part and requires
it echoed back on the next turn. Reconstructing the part discards it, so the
follow-up request was rejected — meaning **no tool call could ever complete**.

**Fix:** never reconstruct the model's turn. Append the actual candidate content
object, which preserves the signature and any fields the SDK adds later:

```python
model_content = response.candidates[0].content
contents.append(model_content)
```

This is the general rule for tool loops: echo back what you received, verbatim.

### Bug 2: `TypeError: unsupported format string passed to NoneType`

```python
f"{currency} {p.get('price'):.0f}"   # price was None
```

**Cause:** hits arriving from Qdrant carry only what was indexed — `sku` and
`name`. No price, no stock. Formatting `None` crashed the whole reply.

**Fix, two parts.** The shallow one: never format a missing value; show
"price on request" instead of guessing a number.

The real one: **product hits are now hydrated from Postgres before use.** The
vector store is for *finding* things, never for quoting them — its payload holds
whatever the price was at index time, so serving from it would quote stale prices
and stale stock after any catalog edit. Postgres is the only source of truth for
money. Indexed products that no longer exist are dropped rather than offered.

---

## Part 2 — Can one project serve all those business types?

**Yes for products. Not yet for appointments** — and the reason why is worth
understanding, because it's the line between config and code.

### What actually varies between your examples

| business | what it needs |
|---|---|
| single product seller | ordering only — no search, there's one SKU |
| reseller / boutique | catalog + ordering |
| hair care, skincare | catalog + ordering + consultation (need-based filtering) |
| home baker | ordering + consultation (made to order, not stocked) |
| salon, clinic | **booking** (+ catalog if they also sell products) |

Look at the first four: they differ only in **which capabilities are switched
on**. None of them needs different conversation logic, because the agent decides
sequencing at runtime. "Single product" isn't a simpler flow — it's the same
ordering capability with one catalog row.

### Built this round: capability kits

`app/agent/capabilities.py` — each tenant gets a kit, and the kit decides which
tools the model can even see:

```
single_product        place_order, review_order, save_order_details,
                      get_order_status, get_shop_info, escalate
                      (no search_catalog — nothing to search)

catalog_seller        + search_catalog

consultative_seller   + consultation prompting (hair care, skincare)

made_to_order         + lead-time behaviour (bakers, tailoring)

service_provider      check_availability, book_appointment, get_shop_info
                      (no place_order — it doesn't sell products)

service_and_retail    everything (salon that also sells shampoo)
```

Onboarding a new client is: pick a kit, upload the catalog, write a paragraph
describing the business. **Zero code.** A salon literally cannot call
`place_order`, and a single-product seller never sees `search_catalog` — fewer
tools means a smaller prompt and fewer wrong turns.

Per-capability guidance goes into the system prompt too, so the bot *behaves*
differently rather than just having different tools. The booking kit, for
instance, is told: never invent a slot, always check availability first.

### The honest limit

**Products and services are different data models, not just config.** A product
has stock; a service has time slots, duration and staff capacity. So:

- `check_availability` and `book_appointment` are **declared but not implemented**
- There's a test that asserts exactly those two are the only unbuilt tools, so
  the gap is visible instead of being discovered when a salon signs up
- A booking client needs: a `services` table, a `slots`/`appointments` table, and
  those two tools. Realistically a few days, not a rewrite

Everything product-shaped works today. Appointments are the one genuinely new
capability, and it's additive — no existing client is touched by building it.

---

## Part 3 — So: platform or per-client automation?

The question dissolves once the architecture is right. **Both, on one codebase.**

| | per-client automation | this codebase |
|---|---|---|
| new client | new project, new flows | pick a kit + upload data |
| bug fix | apply to N projects | fix once |
| your time per client | days | hours |
| asset you own | none | the platform |

Selling it *as* bespoke automation to your first few clients is a perfectly good
strategy — you get paid, and you learn the real flows. The mistake would be
*building* it bespoke, because then client #4 costs the same as client #1 and you
never escape.

My recommendation, unchanged but now with the mechanism to back it:

1. Get 2–3 paying clients live on this codebase, each on a kit
2. Charge them like custom automation if that's easier to sell
3. Let their real transcripts decide what to productise next

---

## Part 4 — What I do next so it behaves correctly for any customer

Priority order:

1. **Verify agent mode actually completes a tool call.** Both bugs above blocked
   every tool call, so agent mode has still never worked end to end. This is the
   only thing that matters until it passes.
2. **Add your real transcripts to the golden set.** Your live sessions have found
   twelve bugs; my invented cases found none of them.
3. **Multi-tenant test.** Two tenants, different kits, confirm no data or
   behaviour leaks between them. Never tested — and it's the core promise.
4. **Alembic migrations.** The first schema change after a client has real orders
   currently loses their data.
5. **Admin panel.** A seller cannot run `python -m scripts.seed_demo`. Without
   this you have a demo you operate, not a product they use.
6. **Booking capability** — when you actually have a service client asking.
7. Payments, jobs, campaigns.

Steps 1–3 are the "behaves correctly for any customer" work. Steps 4–5 are what
make it sellable to a stranger.

---

## What to run

```bash
git pull
docker compose up -d --build
docker compose exec api python -m scripts.eval_harness --delay 13 --verbose
```

Watch for `tool_call` log lines. If you see `search_catalog` followed by a real
reply containing a real price, agent mode works for the first time. If you see
`agent_call_failed` again, paste it and I'll fix the next layer.

Then a live WhatsApp order, end to end, on COD only.

**Commit and push from Windows — nothing here reaches your main laptop until you do.**
