# AI Automation Platform — Pilot Build Plan (Online Product Seller)

## 0. Purpose of this document

This is the build plan for the first working version of the automation platform, piloted on one online product seller (Instagram + WhatsApp based, selling physical products, currently handling every customer conversation manually). Everything here is scoped to ship a real, working pilot at minimum cost — not the full 20-agent "AI company" vision. That vision stays the long-term direction; the module architecture below is designed so it generalizes to it later without a rebuild.

Two things are still open and worth deciding before Phase 0 starts (flagged again at the end): whether this pilot runs against a real seller's actual catalog/WhatsApp number, or a sample catalog first; and how hands-on you want to be in the actual coding versus reviewing what gets built.

---

## 1. What the automation actually solves

The pilot seller's current state: every price question, order, payment follow-up, and shipping update is typed manually into WhatsApp/Instagram DMs, one customer at a time, with nothing recorded anywhere except the chat thread itself.

| # | Problem today | What the automation does |
|---|---|---|
| 1 | Slow replies to "is this available / how much" outside working hours | Answers instantly, 24/7, from the product catalog |
| 2 | Seller manually decides what each message means | AI classifies intent (price question, order, complaint, order status, return) and routes it |
| 3 | Manual back-and-forth to get size/quantity/address | Guided order capture — asks for what's missing, in order, once |
| 4 | Manual price calculation and payment follow-up | Auto-generates quote and a payment link (UPI/COD) |
| 5 | No record of who ordered what | Every order logged to a simple order table, visible in one dashboard |
| 6 | Customer has to ask "where's my order" | Automatic shipping/status updates pushed to the customer |
| 7 | Customers who ask price and vanish are forgotten | Automatic follow-up after a set delay (24h / 48h / discount nudge) |
| 8 | No review requests after delivery | Automatic review/feedback request a few days post-delivery |
| 9 | Complaints handled the same as everything else | Detected and routed straight to the seller — required by WhatsApp policy anyway |
| 10 | Seller has zero visibility into sales patterns | A basic dashboard: orders today, pending payments, top products |

This is deliberately the same 8-10 module set from our earlier module-library discussion — built once here for the pilot seller, config-driven so it's reusable for the next client with a different catalog.

---

## 2. Architecture — the spine and the modules

```
WhatsApp Cloud API (webhook)
        │
        ▼
Channel Adapter (normalizes inbound message)
        │
        ▼
Customer Lookup (existing / new — reads order + chat history)
        │
        ▼
Intent Router (Claude Haiku, tool-calling)
        │
   ┌────┴─────────────────────────────────────┐
   ▼          ▼            ▼          ▼        ▼
Catalog Q&A  Order Capture  Payment  Status   Human Escalation
   │             │            │        │            │
   └─────────────┴────────────┴────────┴────────────┘
                       │
                       ▼
              Order / Customer Database
                       │
                       ▼
        Follow-up Scheduler  +  Admin Dashboard
```

- **Channel adapter**: one webhook endpoint that receives every inbound WhatsApp message and normalizes it into one internal format. (Instagram DM can be added later as a second adapter feeding the same router — not in pilot scope.)
- **Intent router**: a single AI call per incoming message, using tool-calling so the model picks which module handles it (this *is* the "AI receptionist" from earlier conversations, just implemented as a function-calling loop instead of a separate agent).
- **Modules**: each one is a plain function reading from the seller's config/catalog — swapping to a different seller later means swapping the config, not the code.
- **Database**: one small Postgres (or even SQLite for the pilot) database — customers, orders, catalog, conversation log, opted-in contacts.
- **Follow-up scheduler**: a simple cron/queue job that checks for abandoned inquiries, pending payments, and post-delivery timing, and fires the relevant template message.
- **Admin dashboard**: the seller's one screen — pending orders, today's conversations flagged for human attention, and the one-click campaign sender from our earlier discussion.

Everything downstream of the intent router is a "module" in the sense we discussed — this pilot builds ~6, the full vision has ~15, and the difference is just which ones are switched on per client.

---

## 3. Tech stack — optimized for lowest cash cost

| Layer | Choice | Why | Cost |
|---|---|---|---|
| WhatsApp access | Meta Cloud API directly, via Embedded Signup (register as your own Meta Tech Provider) | No BSP markup on top of Meta's own per-message fee | $0 platform fee, pay only per-message |
| Backend | Node.js (Express) or Python (FastAPI) | Free, huge library support, easy webhook handling | $0 |
| Database | PostgreSQL (Supabase free tier is fine for pilot) | Free tier covers pilot volume easily | $0 |
| AI model | Claude Haiku 4.5 for intent detection + replies | Cheapest capable model; ~$1/$5 per million input/output tokens | A few $/month at pilot volume |
| Hosting | Render.com or Fly.io free/starter tier, or a $5/mo VPS (Hetzner/DigitalOcean) | Enough for one pilot client's traffic | $0–10/month |
| Payments | Razorpay (or regional equivalent) for UPI/card links | No fixed fee, ~2% per transaction — paid from revenue, not upfront | $0 upfront |
| Admin dashboard | Minimal React/Next.js page, or even a live Google Sheet + simple internal tool for v0 | Keeps build time down; upgrade later | $0 |
| Templates | Built directly in Meta's WhatsApp Manager / via API | Free to submit; only the message volume costs | $0 |

**No-code alternative**, if you'd rather not hand-code the orchestration layer: self-hosted **n8n** (free, open-source) as the workflow engine connecting WhatsApp Cloud API + Claude API + a spreadsheet or Postgres. Slower to scale into the full multi-agent vision later, but the fastest and cheapest path to a working pilot if you want to see it running before investing in custom code.

**Realistic all-in monthly cash cost to run the pilot**: roughly **$10–30/month** (hosting + AI tokens + occasional WhatsApp template fees), plus the ~2% payment gateway fee that only applies when a sale actually happens. The dominant cost is your own build time, not cloud/API bills.

---

## 4. Build phases

**Phase 0 — Setup (before any code)**
Confirm the pilot seller (real client or sample catalog — see open question below). Create a Meta Business Portfolio + WhatsApp Business Account, get a test number, request API access. Draft the seller's product catalog into a structured format (spreadsheet is fine to start).

**Phase 1 — Core spine**
Webhook receiver, message normalization, customer lookup, intent router with Claude Haiku tool-calling. At the end of this phase, the bot can receive a message and correctly classify what the customer wants — no replies yet.

**Phase 2 — First three modules**
Catalog Q&A (answer price/availability/variant questions from the seller's product list), Order Capture (collect what's missing: size, quantity, address), Payment (generate a Razorpay/UPI link and log the order as pending).

**Phase 3 — Fulfillment loop**
Order status updates pushed automatically as the seller marks an order shipped/delivered in the dashboard. Submit and get approval for the WhatsApp templates needed (order confirmation, shipping update, review request, abandoned-inquiry follow-up, generic promo) — do this early since approval, while usually fast, isn't instant.

**Phase 4 — Retention loop + dashboard**
Abandoned-inquiry follow-up scheduler, review-request automation, the admin dashboard (orders, pending payments, one-click campaign sender), and the mandatory human-escalation path for complaints.

**Phase 5 — Pilot live + observe**
Run it on the real seller's actual traffic for a few weeks. Watch WhatsApp's quality rating, watch which messages the AI mishandles, tune the catalog/templates. This is also when you find out which of the modules were actually seller-specific versus truly generic — the input for building module #2 for your next client.

---

## 5. Open decisions before starting

1. **Real pilot or sample catalog?** Building against an actual seller's real product list and real WhatsApp number from day one keeps the build honest, but requires them to be verification-ready (Meta business verification, a dedicated number). Starting with a sample catalog first is slower to become a real pilot but lets development start immediately.
2. **How hands-on do you want to be?** I can scaffold and write the actual backend code, webhook handlers, and database schema directly — happy to start on Phase 1 now if you want to move straight from plan to working code.
