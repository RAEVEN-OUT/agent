# AI Employee Platform — Build Spec & Roadmap

**Pilot client:** Hair care product seller (Instagram + WhatsApp, direct-to-consumer)
**Long-term goal:** Multi-tenant AI automation platform for SMEs, expanding to enterprise
**Status:** Pre-Phase 1. Stack locked. Awaiting credentials.

---

## 1. What we're building

One platform. One codebase. Many tenants.

Each tenant (client business) gets what feels like a full staff — a salesperson who never sleeps, an order clerk, a follow-up assistant, a bookkeeper — but is really the same core engine reading that tenant's own uploaded data and config. The "AI employee/department" framing is how it's sold; config-driven modules on a shared spine is how it's built.

Non-goals for the pilot: not building 20 separate AI agents, not building an HR module for a 2-person business, not integrating with ERPs nobody has yet.

---

## 2. Pilot vertical: hair care seller

### Why this vertical works as a demo

Real SKUs, real stock to track, and — uniquely valuable — genuinely **predictable repeat purchases**. A 200ml bottle lasts roughly two months, so replenishment timing is forecastable. Manual sellers almost never follow up consistently, so this is where automation produces revenue the seller was previously losing outright.

### The restriction that matters (vertical-specific)

WhatsApp's Business Messaging Policy prohibits **medical and healthcare products**. Ordinary cosmetic hair care is permitted; therapeutic claims are not. Language like "cures hairfall," "treats alopecia," "regrows hair," or "clears scalp infection" risks reclassification as a healthcare product, which can restrict or ban the business number. The same policy discourages using WhatsApp to exchange health-related information.

**Consequence for the build:** a hard **claims guardrail** layer sitting above RAG grounding — not merely a prompt instruction. The bot never promises therapeutic outcomes, never diagnoses a scalp condition, and routes anything medical to a human.

**Non-negotiable safety rule:** any report of an adverse reaction (irritation, allergy, burning) goes straight to a human with no automated reply. This is never tier-gated and never optimized away.

**Customer-sent photos:** people will send scalp/hair photos asking what to use. The bot acknowledges, attaches the photo to the conversation, escalates to the seller — it does not diagnose. Retention of such images is minimized; there's no business reason to keep them long-term.

---

## 3. What the automation solves

| # | Problem today | What the system does |
|---|---|---|
| 1 | Price/availability questions unanswered outside working hours | Instant 24/7 answers from the seller's own catalog |
| 2 | Seller manually interprets every message | Routes by intent: enquiry, order, status, complaint, medical, return |
| 3 | Repetitive back-and-forth to collect order details | Guided capture — asks only for what's missing |
| 4 | No structured product guidance | Consultation intake (hair type, concern, budget) → regimen recommendation |
| 5 | Manual price calc and payment chasing | Auto quote + UPI/COD payment link |
| 6 | Orders live only in chat threads | Every order recorded, visible in one dashboard |
| 7 | "Where's my order?" answered by hand | Automatic status/shipping updates |
| 8 | Enquiries that go quiet are forgotten | Scheduled follow-ups (24h / 48h / offer) |
| 9 | Refills never followed up | Replenishment reminders timed to product size and purchase date |
| 10 | No review collection | Automated review/testimonial request post-delivery |
| 11 | Complaints and reactions handled ad hoc | Detected and escalated immediately to a human |
| 12 | Zero visibility into the business | Dashboard: orders, pending payments, top products, escalation count |
| 13 | Risk of policy-violating claims | Claims guardrail prevents therapeutic language |

---

## 4. Packages — features and restrictions

The tier line is a single rule: **what happens when the cheap path isn't confident.**
Basic hands off to the human owner. Pro hands off to the LLM.

### Basic

**Included:** semantic + keyword catalog search; canned small-talk handling; guided order capture (deterministic slot-filling); payment links; order status updates; scheduled follow-ups; review requests; approved-template campaign sending with one-click admin approval; dashboard; WhatsApp channel.

**Restrictions:** templated reply composition (no free-form generation); no consultative recommendation or regimen building; no objection handling; session-only memory (no long-term customer history); single channel; monthly contact/conversation cap; no custom connectors.

**Positioning:** "You never miss a message, and your business is finally organized." Not "an AI salesperson."

### Pro

**Adds:** LLM intent routing; consultative intake and regimen recommendation; objection handling; full long-term customer memory; bundle/cross-sell logic; replenishment intelligence; multi-channel (Instagram, website); connectors (Sheets, calendar, courier, accounting); analytics insights and recommendations.

**Restrictions:** fair-use conversation cap; connector list limited to supported set.

### Enterprise (later phase)

Dedicated deployment, SSO, audit logs, custom modules, SLA, ERP integration, data residency options, BYO API key.

### Never tier-gated

Human escalation for medical questions, adverse reactions, and complaints. Opt-out honoring. Claims guardrail. These are safety and compliance, not features.

---

## 5. Architecture

```
WhatsApp Cloud API (webhook)
        │
        ▼
Channel Adapter  ── normalizes inbound message
        │
        ▼
COST CASCADE ── returns as soon as any step is confident
  1. Normalize + gibberish filter        (zero cost)
  2. Small-talk / canned intent match    (zero cost)
  3. Response cache (versioned)          (zero cost)
  4. Local follow-up rewrite heuristic   (zero cost)
  5. Keyword search over catalog/FAQ     (near-zero)
  6. Cached embedding → Qdrant search    (cheap)
  7. LLM  ← last resort, not first move
        │
        ▼
Customer Lookup  ── history, orders, preferences
        │
        ▼
Intent Router (LLM, tool-calling)  [Pro]  /  Fixed flow  [Basic]
        │
   ┌────┴──────────────────────────────────────────────┐
   ▼        ▼         ▼        ▼        ▼        ▼      ▼
Catalog  Consult  Order    Payment  Status  Replenish  Escalate
 Q&A     Intake   Capture   Link    Update   Reminder   to Human
   │        │         │        │        │        │        │
   └────────┴─────────┴────────┴────────┴────────┴────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   PostgreSQL       Qdrant        Event Bus
  (orders, CRM,   (RAG chunks)   (order.created,
   catalog, plans)                payment.received, …)
        │                              │
        ▼                              ▼
  Admin / ERP Panel            Connectors (Sheets,
  (Next.js)                     Telegram, courier…)
```

### Key design rules

**Cache facts, not conversations.** The cascade's fast-paths exist to skip *retrieval* work, not *sales judgment*. A price question does a zero-cost lookup for price and stock, then spends one cheap LLM call to compose a reply that answers *and* sells. Fully canned replies are reserved for messages containing no sales judgment at all (greetings, business hours, shipping zones, "talk to a human").

**Never fast-path advisory questions.** Comparative or consultative messages ("which is better for dry hair," "what suits my budget") must reach the reasoning layer regardless of keyword-match confidence. Those are the conversations that earn money.

**Business logic ordering is enforced; conversation ordering is not.** The AI can raise cross-sells before, after, or never relative to closing. But it cannot mark an order shipped before payment clears, or invoice without an address. Preconditions guard the transaction, not the dialogue.

**Grounded, not generative.** Every tenant upload (catalog, policies, FAQs, bot rules) is chunked into Qdrant, scoped by `tenant_id`. Retrieval returns only that tenant's data, and the model answers only from what was retrieved — if nothing relevant returns, it says so and escalates. Updating the bot's knowledge is re-uploading a file, not a code change.

**One codebase, isolated data.** `tenant_id` scoping on every row and every vector payload, plus a plan-flags table driving tier behavior. Docker means any tenant can still be given a physically separate container and database when warranted — without a code fork.

---

## 6. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python + FastAPI | Matches existing chatbot pipeline; proven pieces reusable |
| Relational DB | PostgreSQL | Orders, customers, catalog, plans, usage metering |
| Vector DB | Qdrant | Multi-tenant via payload filters; existing service code reusable |
| Cache / state / queue | Redis | Response cache, embedding cache, session state, rate limits, usage counters |
| Background jobs | arq (Redis-backed) | Follow-ups, replenishment, campaigns, send retries |
| LLM | Gemini Flash primary, fallback behind same wrapper | Provider-agnostic interface; cheap-first with failover |
| Embeddings | Gemini embedding API | Cached; self-hosted option deferred (see caveat) |
| Frontend | Next.js | Admin panel and tenant ERP in one platform |
| Auth | Firebase | Fast to stand up, free tier adequate |
| WhatsApp | Meta Cloud API direct | Version pinned as single config value |
| Packaging | Docker Compose | Backend, Postgres, Qdrant, Redis |
| Extensibility | Event bus + outbound webhooks | Connectors in-code; n8n optional consumer later |

### Caveats to manage

**Dual-store consistency.** Postgres and Qdrant share no transaction. Catalog writes must update both, deletes must purge vectors, and a periodic reconciliation job must catch orphans. (The existing codebase already carries a fix for exactly this class of bug — stale vectors returning outdated answers.)

**Embedding model migration.** Switching to a self-hosted model later is not a config flip: different dimensions and vector space require regenerating every vector and recreating the collection. Mitigation — always retain source text, and record model + dimensions per collection. The existing cache key already namespaces by model name; keep that discipline.

**WhatsApp API versioning.** Cloud API versions are supported roughly two years. Nothing breaks overnight; expect a version bump every 1–2 years plus a changelog review. Pinned in one config value so this stays a five-minute change.

---

## 7. Unit economics

Per-tenant monthly cost structure:

- **LLM:** fractions of a cent per conversation on a cheap model (~$37 per 10,000 support-style conversations as a published reference point). A few dollars/month at SMB volume. Basic tier approaches zero.
- **WhatsApp:** per delivered message, by category and country. Service-window replies are free. Marketing sends are the real variable.
- **Infrastructure:** shared across tenants; tens of dollars/month until meaningful scale.
- **Payments:** ~2% per transaction, incurred only on actual sales.

**Billing principle:** never bill clients on tokens — meaningless to a shop owner and produces unpredictable invoices. Bill on units they understand: conversations handled, orders processed, or contacts messaged. Keep tokens as the internal cost metric, metered per tenant from day one so margin per client is always known.

**Built-in upsell metric:** because Basic escalates to the human, the dashboard already counts escalations. That produces the most honest upgrade pitch available — "you handled 40 escalations manually this week; Pro would have closed 35 automatically."

---

## 8. Roadmap

Phases 0–3 build the pilot. Phases 4–9 build the company. Note that from Phase 4 onward, **the gate to advance is commercial evidence, not code completion** — building the next layer before the current one has paying, retained users is the most common way platforms like this die.

### Phase 0 — Setup
Meta Business Portfolio + WhatsApp Business Account via Embedded Signup (dev number). Gemini API key. Firebase project. Catalog and policies for the pilot seller collected into structured form. Docker skeleton running locally.

### Phase 1 — Core spine
Webhook receiver, message normalization, gibberish filter, small-talk fast-path, response cache, tenant resolution, customer lookup, intent router with tool-calling. Outcome: an incoming message is correctly classified. No replies yet.

### Phase 2 — Commerce modules
Catalog Q&A (grounded retrieval + composed reply), consultation intake, claims guardrail, order capture with stock check, payment link generation. Outcome: a customer can go from "how much?" to a paid order without the seller typing.

### Phase 3 — Fulfillment, retention, admin
Status updates, replenishment scheduler, review requests, follow-up sequences, escalation routing, campaign sender with one-click approval, WhatsApp template library submitted and approved, Next.js admin panel with catalog upload and bot-rules configuration. Outcome: a complete, shippable single-tenant product.

**Gate to Phase 4:** the pilot seller uses it daily, unattended, for several weeks — with WhatsApp quality rating healthy and escalation rate falling.

### Phase 4 — Productize multi-tenancy
Self-serve tenant provisioning, plan flags enforcing Basic/Pro, per-tenant usage metering and rate limits, subscription billing, tenant onboarding flow, admin-of-admins view. Outcome: onboarding client #2 requires no engineering.

**Gate:** several paying tenants onboarded without developer involvement.

### Phase 5 — Vertical packs
Config bundles, not code forks: Boutique Pack, Bakery Pack, Food Pack, Reseller Pack — each a module selection, an intake question set, a template library, and tone/escalation defaults. Outcome: new verticals sold without new codebases.

### Phase 6 — Channel expansion
Instagram DM and comments, website widget, email, later voice. All feed the same router through additional channel adapters. Outcome: genuinely omnichannel — one brain, many doors.

### Phase 7 — Connector layer
Google Sheets, Calendar, courier APIs, accounting, Shopify/WooCommerce, Power BI export. Built as event-bus consumers, enabled per tenant by config. This is where "glue" requests scale without polluting the core. Outcome: the platform integrates into whatever the client already runs.

### Phase 8 — Intelligence layer
The higher "AI employee" functions become credible only once there's data history: nightly business digests, demand and stock forecasting, churn and repeat-purchase prediction, marketing campaign generation, an owner-facing "why were sales down?" assistant. Outcome: shifts from automation to decision support — the hardest thing for a competitor to replicate, because it's built on accumulated tenant data.

### Phase 9 — Enterprise readiness
Security and compliance posture (audit logs, SSO, encryption review, penetration testing, SOC 2-style controls), data residency options, dedicated/on-prem deployment, SLA and support tiers, ERP integration adapters, BYO API key. Outcome: sellable to businesses that already have systems and a procurement process.

---

## 9. Honest risks

**Platform dependency.** Meta controls pricing, policy, template approval, and number bans. It has already changed pricing models once. A policy shift or a quality-rating drop can degrade the product overnight, through no fault of the code. Mitigation: build channel-agnostic from the start (Phase 6 matters strategically, not just commercially) so WhatsApp is one door, not the foundation.

**Meta's own Business Agent competes at the shallow end.** It already handles FAQs, catalog browsing, and basic booking. Differentiation must stay in operations — inventory, orders, memory, fulfillment, reporting — not conversational polish.

**Support burden, not code, is what breaks small SaaS.** At 30+ tenants, onboarding, catalog cleanup, and "why did the bot say that?" tickets consume more time than development. Phases 4–5 exist largely to make onboarding self-serve before this bites.

**Regulated verticals need care.** Hair care sits adjacent to prohibited healthcare messaging; skincare more so. The claims guardrail is load-bearing, and vertical expansion into anything health-adjacent needs review, not just a new config pack.

**Accuracy risk from the cost cascade.** Fast-paths firing when they shouldn't produces confidently wrong answers. Confidence thresholds need tuning against real message logs before being trusted in production.

**LLM provider pricing and model changes.** Mitigated by the provider-agnostic wrapper and cheap-first-with-fallback pattern.

---

## 10. What's needed to start Phase 1

Credentials and account steps only you can complete:

1. **WhatsApp** — complete Meta Embedded Signup on your number. Provide: permanent access token, Phone Number ID, WhatsApp Business Account ID.
2. **Gemini** — API key from Google AI Studio.
3. **Firebase** — project created; provide config/service account.
4. **Payments** — Razorpay (or equivalent) account; needed only at Phase 2, requires KYC.

Development proceeds against mock data until each arrives. Secrets go in `.env`, never in the repo or in chat.
