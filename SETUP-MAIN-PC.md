# Setup guide — main laptop

Everything runs here. The Cowork machine only writes code and pushes to GitHub.

**Read this once, then use the "Daily workflow" section from then on.**

---

## 0. The one thing that will trip you up

`.env` and `firebase-service-account.json` are **gitignored on purpose**. They
will *not* arrive with `git pull`. You have to create them by hand on this
laptop, once. Everything else comes down with the repo.

Both go at the **repo root** (`D:\Project\agent\`), not inside
`whatsapp-ai-employee\`, because docker-compose mounts them from `../`.

Expected layout after setup:

```
D:\Project\agent\
├── .env                            <- you create (never committed)
├── firebase-service-account.json   <- you copy (never committed)
├── CLAUDE.md
├── SETUP-MAIN-PC.md
├── ai-employee-platform-spec.md
├── credentials-setup-checklist.md
└── whatsapp-ai-employee\
    ├── docker-compose.yml
    ├── app\  scripts\  tests\
    └── README.md
```

---

## 1. Install (one time)

| Software | Why | Notes |
|---|---|---|
| **Git** | pull the code | https://git-scm.com |
| **Docker Desktop** | runs api + Postgres + Redis + Qdrant | Windows: enable the **WSL2 backend** in Settings → General. Must be *running* before any `docker compose` command. |
| **ngrok** | public HTTPS URL for the WhatsApp webhook | https://ngrok.com — free account is fine. `cloudflared` works too. |
| **Python 3.12** *(optional)* | run tests outside Docker | Not required; tests run fine inside the container. |
| **VS Code** *(optional)* | editing | |

Verify Docker before continuing:

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

If `hello-world` fails, fix Docker first — nothing else will work.

---

## 2. Get the code

```powershell
cd D:\Project
git clone https://github.com/RAEVEN-OUT/agent.git
cd agent
```

If the folder already exists, just `git pull` instead.

Set line endings once (avoids Windows CRLF noise in diffs):

```powershell
git config core.autocrlf input
```

---

## 3. Create the secrets

**3a. `.env` at the repo root.** Copy the template and fill in your values:

```powershell
copy whatsapp-ai-employee\.env.example .env
notepad .env
```

Fill in from `credentials-setup-checklist.md`:

- `WHATSAPP_ACCESS_TOKEN` — the **System User** token, not the 24-hour one from
  the API Setup panel
- `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET`
- `WHATSAPP_VERIFY_TOKEN` — any random string you invent; must match what you
  type into the Meta dashboard later
- `GEMINI_API_KEY`
- Firebase web config values (needed at Phase 3, harmless to leave empty now)

Leave the Postgres/Redis/Qdrant values as they are — docker-compose overrides
them with the container hostnames automatically.

**3b. `firebase-service-account.json`** — copy the file you downloaded from
Firebase to `D:\Project\agent\firebase-service-account.json`.

> Move these two files between machines with a USB drive, password manager, or
> any private channel — never by committing them, and never by pasting them into
> a chat.

---

## 4. First run

```powershell
cd D:\Project\agent\whatsapp-ai-employee
docker compose up --build
```

First build takes a few minutes. Wait for:

```
{"event": "startup", ...}
{"event": "tables_ready", ...}
Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal running. Open a **second terminal** for everything below.

### 4a. Check credentials and infra

```powershell
cd D:\Project\agent\whatsapp-ai-employee
docker compose exec api python -m scripts.verify_credentials
```

You want `PASS` on all four lines. This is the fastest way to catch a bad token
before anything else confuses you.

### 4b. Seed the pilot tenant

```powershell
docker compose exec api python -m scripts.seed_demo
```

Creates the "Glow Roots" hair care tenant, 8 products, 7 FAQs, and indexes them
into Qdrant.

> Re-run this any time you change `WHATSAPP_PHONE_NUMBER_ID` — the tenant is
> matched to incoming webhooks by that ID, and a mismatch means the bot silently
> ignores every message (you'll see `unknown_tenant` in the logs).

### 4c. Talk to the bot with no WhatsApp involved

```powershell
docker compose exec api python -m scripts.simulate_chat --script
```

This is the best thing to run first. It pushes 18 messages through the real
orchestrator and prints which cascade step answered each one and what it cost.

Then compare the tiers — this is the clearest demo of Basic vs Pro:

```powershell
docker compose exec api python -m scripts.simulate_chat --plan basic --script
docker compose exec api python -m scripts.simulate_chat --plan pro --script
```

Interactive mode:

```powershell
docker compose exec api python -m scripts.simulate_chat --verbose
```

### 4d. Run the tests

```powershell
docker compose exec api python -m pytest -q
```

Expect `65 passed`.

---

## 5. Connect real WhatsApp

**5a. Start the tunnel** (third terminal, leave running):

```powershell
ngrok http 8000
```

Copy the `https://` forwarding URL, e.g. `https://a1b2c3d4.ngrok-free.app`.

**5b. Register the webhook** in the Meta App Dashboard →
**WhatsApp → Configuration → Webhook → Edit**:

- **Callback URL:** `https://a1b2c3d4.ngrok-free.app/webhook`  (no trailing slash)
- **Verify token:** exactly the `WHATSAPP_VERIFY_TOKEN` from your `.env`
- Click **Verify and save** — you should see
  `{"event": "webhook_verified"}` in the api logs
- Then **Manage** the webhook fields and subscribe to **`messages`**

**5c. Send a message.** From the phone you added as a test recipient, message
the test business number. Try:

```
hi
how much is the argan oil
which shampoo is good for dandruff
```

Each inbound message logs a line containing `handled_by`, `intent`, `llm_calls`
and token counts.

> **ngrok free URLs change on every restart.** Whenever you restart ngrok you
> must re-register the callback URL in the Meta dashboard. A reserved/static
> domain on a paid ngrok plan removes this chore.

---

## 6. Daily workflow

```powershell
cd D:\Project\agent
git pull                                   # get the code I wrote

cd whatsapp-ai-employee
docker compose up                          # or: docker compose up --build
                                           # (--build only if requirements.txt changed)

# second terminal
docker compose exec api python -m pytest -q
docker compose exec api python -m scripts.simulate_chat --script
```

If you edit code yourself and want it back to me:

```powershell
git add -A
git commit -m "describe the change"
git push
```

Useful container commands:

```powershell
docker compose logs -f api          # follow logs
docker compose restart api          # restart just the api
docker compose down                 # stop everything (data survives)
docker compose down -v              # stop and WIPE Postgres + Qdrant data
```

After `down -v` you must re-run `seed_demo`.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker: error during connect` | Docker Desktop isn't running. Start it and wait for the whale icon to settle. |
| `verify_credentials` → error **190** | Token expired or invalid. You used the temporary 24-hour token — create a System User token (checklist §1f). |
| `verify_credentials` → embedding **WARN** about dimensions | Gemini returned a different vector size. Set `GEMINI_EMBEDDING_DIMENSIONS` to the reported number in `.env`, then `docker compose down -v`, `up`, and re-run `seed_demo`. Vector search silently returns nothing otherwise. |
| Meta "Verify and save" fails | ngrok not running, wrong URL, trailing slash on the URL, or verify token doesn't match `.env`. Check the api logs for `webhook_verify_failed`. |
| Webhook returns 403 on real messages | `WHATSAPP_APP_SECRET` is wrong — signature check fails. (Only for local `curl` testing, you can set `VERIFY_WEBHOOK_SIGNATURE=false`. Never in production.) |
| Messages arrive but bot never replies | `unknown_tenant` in the logs → the seeded tenant's `whatsapp_phone_number_id` doesn't match your current `.env`. Re-run `seed_demo`. |
| `port is already allocated` (5432 / 6379 / 8000) | You already run Postgres/Redis/something on that port. Stop it, or change the left-hand side of the port mapping in `docker-compose.yml` (e.g. `"5433:5432"`). |
| Bot replies "Let me check that with our team" to everything | Either `GEMINI_API_KEY` is missing (check `verify_credentials`) or nothing was seeded (`seed_demo`). |
| Everything worked yesterday, dead today | The WhatsApp token was temporary. See error 190 above. |

---

## 8. What is not built yet

Phase 1 only. Deliberately missing (see `ai-employee-platform-spec.md`):

- Razorpay payment links — orders record the method and total, no link yet
- Follow-up / replenishment / campaign schedulers
- Next.js admin panel — catalog changes go through `scripts/seed_demo.py`
- Alembic migrations — currently `create_all` on startup
- Postgres ↔ Qdrant reconciliation job
