# Answer — 30 July 2026 (eighth update): templates vs capabilities, analysed

First: you're right that I over-stepped. You asked me to research and compare, and
I shipped code instead. That's a pattern I should break — you can't evaluate a
recommendation you didn't get to weigh. This one is analysis first.

Your run: **30/31 (97%)**. The one failure is my test being wrong, not the bot —
explained at the end.

---

## 1. How this is actually solved at scale

The multi-vertical problem is old and the industry converged on one answer. Look at
who solved it and what shape their solution has:

| company | the platform | the vertical layer | the long tail |
|---|---|---|---|
| Salesforce | one CRM core | **Clouds** (Sales, Service, Health) | AppExchange |
| HubSpot | one CRM core | **Hubs** (Marketing, Sales, Service) | marketplace |
| Shopify | one commerce core | **themes + app bundles** | App Store |
| Zoho | one data spine | ~50 apps sharing it | marketplace |
| Sierra / Intercom Fin | one agent runtime | per-company **playbooks / actions** | custom actions |
| WhatsApp BSPs (Wati, Gupshup, Interakt) | one messaging core | **per-vertical flow templates** | custom flows |

The pattern is identical everywhere:

> **Composable platform. Templated go-to-market. Marketplace for what you can't
> anticipate.**

Two things nobody does: fork the code per customer, or ship one generic
configuration and expect the customer to figure it out.

**The SMB-specific lesson is sharper.** Shopify didn't beat Magento on features —
it beat it on *time to first sale*. In the SMB segment the winner is decided by
onboarding speed, not by how clever the product is. That is the single strongest
argument for your template idea, and it's a commercial argument, not a technical
one.

---

## 2. Your plan vs my plan — honest comparison

I had built **capability kits**: per-tenant tool toggles. You proposed **templates**:
productised bundles per business type.

| | my capability kits | your templates |
|---|---|---|
| decides which tools run | yes | yes |
| data schema the client must supply | **no** | yes |
| what to ask before recommending | no | yes |
| WhatsApp outbound templates | **no** | yes |
| what "success" means for this business | **no** | yes |
| an onboarding form you can hand a client | **no** | yes |
| something you can name and price | **no** | yes |

### Verdict

**They are not competing designs. Yours is the layer mine was missing.**

A template is a superset: `template = capabilities + data schema + intake +
outbound templates + goal + onboarding form`. My kits were an implementation
detail with no commercial expression — I could not have answered "what am I
selling?" or "what do I ask the client for?" with them.

**And yours forced decisions mine had quietly skipped.** The most important:
*success is not the same in every business.* An interior designer's bot that
quotes a price has done damage. A consultancy bot that never closes has failed.
My kits had no concept of a goal, so both bots would have behaved identically and
one of them would have been wrong. That gap only became visible because you named
"enquiry-based" as a category.

So: my plan was the engine; yours is the product. The engine still matters — see
the next section for why templates *alone* would have been the wrong call.

---

## 3. Mix and switch — and the trap templates have on their own

You asked whether templates can mix, switch, and attach like modules. This is the
question that decides the architecture, because **pure templates fail here.**

If templates were hard-coded bundles, real businesses would break them
immediately:

- a salon that also sells retail products
- a baker who also runs paid classes
- a boutique that takes custom orders *and* stocks ready-made
- a clinic that sells supplements

Hard bundles mean combinatorial explosion — you'd end up writing
`salon_plus_retail`, `bakery_plus_classes`, and you're forking again with extra
steps.

**So the right structure is: templates as presets over composable capabilities.**
That is exactly what Salesforce Clouds and Shopify themes are — opinionated
starting points on a composable core, not walls.

Concretely, in what's now built:

```
template  ->  capabilities  ->  tools
"consultancy" -> CATALOG, CONSULTATION, ORDERING, ORDER_STATUS, SHOP_INFO
              -> search_catalog, save_order_details, review_order, place_order, ...
```

And a tenant can override the preset with an explicit capability list, so a
salon-with-retail is config, not a new template.

### What's genuinely easy vs hard to switch

| change | difficulty | why |
|---|---|---|
| swap template within the same data shape (catalog ↔ consultancy ↔ single product) | **trivial** — one SQL update | same tables, same tools, different prompts |
| add one capability to a tenant | **trivial** — config line | capabilities compose |
| product business → service/booking | **hard** — migration | services need slots, duration, staff capacity: a different data model |
| change vertical after going live | **hard** | approved WhatsApp templates are vertical-specific and need re-approval |

That last row is the one people miss. Tools switch instantly; **Meta-approved
message templates do not.** A bakery's "your cake is ready for pickup" cannot be
reused by a salon. So switching vertical late costs template-approval time, which
is days, not minutes.

---

## 4. What templates are needed — from the market, not imagination

Ordered by how many Indian SMBs actually fit each:

| # | template | fits | state |
|---|---|---|---|
| 1 | **Catalog retail** | boutiques, resellers, general stores, COD sellers | ✅ built |
| 2 | **Consultancy retail** | hair, skin, supplements, ayurveda, pet care | ✅ built |
| 3 | **Appointment / service** | salon, clinic, tuition, repairs, studios | ❌ **needs new data model** |
| 4 | **Made to order** | bakers, tailors, printers, custom gifting | ✅ built |
| 5 | **Enquiry / lead capture** | real estate, interiors, B2B, events | ✅ built |
| 6 | **Single product** | one hero product, course, device, subscription | ✅ built |
| 7 | Food / restaurant | daily menu, time windows, no persistent stock | ❌ distinct from catalog |
| 8 | Hyperlocal grocery | repeat baskets, substitutions, delivery slots | ❌ distinct |

**My recommendation: do not build 8. Ship the 5 you have.**

Reasoning: templates 1, 2, 4, 5, 6 already cover a very large share of WhatsApp-
selling SMBs, and every one of them shares the product/order data model — so
they're proven by the same testing. #3 (appointments) is the biggest genuine gap
and the largest untapped segment, but it needs new tables, so build it when a real
service client is asking, not speculatively. #7 and #8 are real but narrower, and
each wants its own data model too.

Building templates for clients you don't have is the same mistake as building a
platform for clients you don't have.

---

## 5. Where templates could still go wrong

Being honest about the risks of your idea, since I'm endorsing it:

1. **Preset rigidity** — mitigated by composition (section 3), but only if we keep
   resisting the urge to hard-code hybrids.
2. **Template sprawl** — 8 templates × 6 layers each is a lot of surface to keep
   correct. Every template needs its own golden-set cases or it will rot silently.
   Right now only the consultancy template is actually tested against real messages.
3. **False confidence in the goal** — "enquiry never quotes" is enforced by
   withholding tools, which is solid. But "consultancy should close" is only a
   prompt. Prompts drift; tool absence doesn't.
4. **Onboarding data quality** — the template tells the client what to supply, but
   a messy catalog still produces a messy bot. The admin panel matters more than
   more templates.

---

## 6. Your two behaviour complaints — fixed

### "Hi Eval!" every time

You were right, and my previous fix was too narrow: I only suppressed greetings
*mid-conversation*, so in the eval (where every case is a fresh conversation) it
greeted every time. But the deeper problem is that `Hi <name>!` as an **opener
formula** is what reads automated, even once.

Now explicitly instructed: never open with "Hi <name>", use the name rarely and
mid-sentence where it adds warmth ("that one's very popular, Raveen"), most replies
use no name at all, and vary the opening between messages.

### Capture the name so non-buyers can be followed up

This was a real gap and a good sales instinct. Added a `remember_customer` tool,
available to **every** template, which stores name, what they were interested in,
and any useful note on the customer record.

Prompt guidance: ask for the name **once**, naturally, at a good moment (taking an
order, or after real interest) — never as an opening line. Save what they
volunteer without announcing it.

The point you made is the important one: *a browser today is a follow-up tomorrow,
and an unnamed contact cannot be followed up properly.* Interest is now stored on
the customer profile, so a "you were looking at the argan oil" follow-up becomes
possible once the scheduler exists.

---

## 7. The one failing case is my test, not the bot

```
FAIL sulphate_free — did not call get_shop_info (called ['search_catalog'])
"Yes, we have the Rosemary Strengthening Shampoo (INR 549 for 200ml) and the
 Rosemary Duo Combo (INR 999), both of which are sulphate-free…"
```

Asked "is it sulphate free", the bot named the actual sulphate-free products with
prices, instead of reciting the generic FAQ line. That is a **better** answer for a
shop, and it was correctly grounded in a real tool call.

My assertion demanded one specific tool. Fixed by adding `expect_tools_any` so a
case can accept either route when both are legitimate. Worth remembering as an
eval-design lesson: assert on the *outcome*, and only pin the mechanism when the
mechanism actually matters.

---

## 8. What I recommend, and what I'm not doing without your say-so

**Recommended, in order:**

1. **Do not build more templates yet.** Sell into the 5 you have.
2. **Admin panel** — the real blocker. A client cannot run `seed_demo`, so today
   you have a demo you operate, not a product they use.
3. **Multi-tenant test** — two tenants, two templates, prove nothing leaks.
4. **Alembic migrations** — `Lead` and any future table currently risk data.
5. **Appointment template** — only when a service client asks.

**Not doing without your go-ahead:** building templates 7 and 8, or the booking
data model. Say the word and I'll start on any of them.

---

## Changes this round (small, only what you asked for)

| file | change |
|---|---|
| `app/agent/loop.py` | no "Hi <name>" openers; sparse mid-sentence name use; vary openings; ask for name once naturally |
| `app/agent/tools.py` | `remember_customer` tool — name, interests, notes |
| `app/agent/capabilities.py` | `remember_customer` always on, every template |
| `scripts/eval_harness.py` | `expect_tools_any` |
| `tests/golden_set.json` | `sulphate_free` accepts either tool |

242 tests passing.

**Commit and push from Windows — nothing here reaches your main laptop until you do.**
