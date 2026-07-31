# Answer — 30 July 2026 (seventh update)

Two things: your eval run went **9/27 → 28/31 (90%)**, and I've built the template
idea properly now that I understand it. **242 tests passing.**

---

## Part 1 — The three remaining failures share one cause

All three are the same mistake: **the bot asked a clarifying question instead of
searching first.**

```
"i want to order ur oil"
→ "To make sure I recommend the right one, what are you looking to achieve?"
   (no tool called; missing 100, missing 200)

"u have shampoo"
→ "Yes, we have a few different shampoos. What hair concerns?"
   (no tool called — "we have a few" is an unverified claim)

"wht products do u sell"
→ "We specialize in natural hair and skincare products."
   (no tool called — pure model knowledge)
```

A real salesperson doesn't answer "do you have shampoo?" with "what are you
looking for?" — they **show you the shelf, then narrow it down.** Two of these
also invented claims: "we have a few different shampoos" and "we specialize
in..." were never verified against the catalog.

**Fixed** with an explicit ordering rule: if the customer names any product,
category or type — or asks what you sell — call `search_catalog` **first** and
show real names and prices, *then* narrow. Only ask before searching when they
describe a problem with no product mentioned ("my hair keeps breaking").

### Watchdog false positive, also fixed

`advisory_open_ended` was flagged ungrounded for "I'm sorry to hear your hair is
feeling fragile… is it colour-treated or heat-styled?" That's empathy plus a
clarifying question — legitimately needing no tool. My heuristic used reply length,
which was crude. It now looks for the *claim itself*: a digit, or phrases like
"we have", "all our", "is available". A pure question no longer trips it.

### Also worth noting from your run

`sulphate_free` is now correct and grounded: *"our shampoos are sulphate-free, and
our entire range is paraben-free"* — matching your FAQ exactly, with a
`get_shop_info` call behind it. Last run it hedged with "many of our products"
from model knowledge. The grounding rule worked.

**Real numbers from your run:** 1.6s average latency, $0.000528/message →
**$1.58/month at 300 conversations.** Close to my $1.72 estimate.

---

## Part 2 — Your template idea, built

You meant: build template-wise automation — consultancy-based, single-product,
enquiry-based — where the client just adds data, and you sell whichever fits.

**That's right, and it's better than what I had.** I'd built capability kits,
which were only the *tools*. A template needs to be the whole package, because
that's what turns onboarding into a form instead of a project.

`app/agent/business_templates.py` — five templates, each bundling six layers:

| | consultancy | single product | enquiry | catalog | made to order |
|---|---|---|---|---|---|
| sells to | hair/skin care, supplements | one hero product, course | real estate, interiors, B2B | boutiques, resellers | bakers, tailors |
| **goal** | close the order | handle objections, close | **qualify — never quote** | find in stock, order | confirm lead time, order |
| tools | 7 | 6 (no search) | **3 (no ordering)** | 7 | 7 |
| WhatsApp templates | 5 | 4 | 2 | 5 | 2 |
| policy questions | 6 | 5 | 4 | 4 | 4 |
| intake questions | 3 | 0 | 4 | 0 | 3 |

### The most important thing this encodes

**Success is not the same in every template.** That's the insight your naming
exposed and my kits missed.

An interior designer's bot that quotes a price has done real damage — either it
undercuts the business or it promises something unachievable. So the enquiry
template *cannot* quote: `place_order`, `save_order_details` and even
`search_catalog` are **not exposed to the model at all**. There is no catalog of
prices for it to read, so there is no price for it to leak. Its only sales tool is
`capture_enquiry`. That's enforced in code, not in a prompt, with tests asserting
those tools are absent.

New this round to make that real: a `Lead` table, a `capture_enquiry` tool, and a
`lead.captured` event.

### The layer I'd argue is your biggest commercial asset

**The WhatsApp template library per vertical.** Every outbound message needs Meta
approval, and they're vertical-specific:

- bakery → "your cake is ready for pickup"
- salon → "your appointment is tomorrow at 4pm"
- hair care → "your 200ml should be running low — reorder?"
- interiors → "our team will call you within 24 hours"

Write them once per template and **every future client in that vertical inherits
already-approved wording** instead of waiting on review. That's compounding
leverage, and it's the thing a competitor building per-client automations can
never accumulate.

All marketing templates include a STOP opt-out — tested — because opt-out
handling is what protects the number's quality rating.

### Onboarding is now a printable form

`onboarding_checklist("enquiry")` outputs exactly what to ask a client for:

```
Business name, and one paragraph describing what you sell
Catalog with these columns: service, description, starting_from, coverage_area
Answers to these policy questions:
    - Which areas do you serve?
    - What is the typical project timeline?
    - Do you charge for a consultation?
    - What are your working hours?
2 WhatsApp templates to submit for approval (pre-written — no wording needed from you)
WhatsApp Business number + Meta business verification
```

That's your sales conversation and your onboarding process, generated from the
template. Setting up a client is: pick the template, fill this in, upload the
catalog.

---

## Changes

| file | change |
|---|---|
| `app/agent/loop.py` | search-before-clarify rule; precise grounding watchdog; template goal in prompt |
| `app/agent/business_templates.py` | **new** — 5 complete templates with WA templates, policy Qs, intake, goals |
| `app/agent/capabilities.py` | `ENQUIRY` capability; templates now drive capabilities |
| `app/agent/tools.py` | `capture_enquiry` tool |
| `app/db/models.py` | `Lead` table |
| `app/services/events.py` | `lead.captured` |
| `tests/test_business_templates.py` | **new** — 24 tests, incl. "enquiry can never quote" |

---

## What to run

```bash
git pull
docker compose up -d --build
docker compose exec api python -m scripts.eval_harness --delay 13 --verbose
```

The three failures should pass — watch for `search_catalog` being called on
`"u have shampoo"` and `"wht products do u sell"`, and both sizes appearing for
`"i want to order ur oil"`.

To try a different template on the same data, set it on the tenant:

```sql
UPDATE tenants SET settings = jsonb_set(settings, '{template}', '"enquiry"');
```

Then message it asking for a price — it should refuse to quote and capture an
enquiry instead. That is the multi-template promise, testable in one command.

---

## Next, unchanged and still blocking a real client

1. **Multi-tenant test** — two tenants, two templates, confirm nothing leaks
2. **Alembic migrations** — the `Lead` table I just added is exactly the kind of
   change that destroys data under `create_all`
3. **Admin panel** — a client cannot run `seed_demo`
4. Backups, monitoring, restart policy on `api`
5. Then payments

**Commit and push from Windows — nothing here reaches your main laptop until you do.**
