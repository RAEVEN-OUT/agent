# Project context for Claude

Read this first in any new session.

## Standing instruction: question.md / answer.md

The user often works from a remote machine and cannot see chat replies there.

**When the user says "read question" (or any variation of it):**

1. `git fetch origin` in the repo root, then read the LATEST question with
   `git show origin/main:question.md`. Do **not** just read the working-tree
   copy — it is usually stale, because this sandbox cannot check out.
2. Answer it, making whatever code changes it requires.
3. **Write the full answer to `answer.md` at the repo root**, overwriting
   whatever was there. This is the deliverable — the user pulls it with git and
   reads it on the other machine.
4. Keep the chat reply short; `answer.md` carries the detail.
5. Tell the user to commit and push (see limitation below).

### Sandbox git limitation — verified, do not retry

From this machine Claude **can**:
- `git fetch` and read any remote file via `git show origin/main:<path>`
- read local files, and Write/Edit files in the working tree

Claude **cannot**:
- `git pull` / checkout — the mount forbids unlinking files
  (`error: unable to unlink old 'question.md': Operation not permitted`)
- `git add` / `git commit` — cannot create or clear `.git/index.lock`
- `git push` — no credentials in the sandbox
  (`could not read Username for 'https://github.com'`)

So the loop is: **Claude writes files → the user commits and pushes from
Windows → the user pulls on the main laptop.** Always end a "read question"
reply by reminding the user to commit and push, since nothing Claude writes
reaches the other machine on its own.

`answer.md` must stand alone: the user reads it without the chat context. Include
what was asked, what was found, what changed, and what to run next. Date it.

## Working arrangement

**Two machines, split roles:**

| | This machine (Cowork) | Main laptop |
|---|---|---|
| Role | write code only | run everything |
| Has Docker / Postgres / Redis / Qdrant | no | yes |
| Network access to Meta + Gemini APIs | **no** (sandbox allowlist blocks `graph.facebook.com` and `generativelanguage.googleapis.com`) | yes |
| Runs the bot | never | always |

**Sync path:** this folder is a git repo (`github.com/RAEVEN-OUT/agent`). Claude
writes code here and commits; the user pulls on the main laptop and runs it there.

**Consequences for Claude:**

- Do not try to smoke-test WhatsApp or Gemini calls from here — they will fail
  with HTTP 000. Verification here is limited to: `python -m compileall`,
  `pytest` (unit tests with no network/DB), and FastAPI `TestClient` checks.
- Anything requiring a live API, a database, or Docker must be handed to the
  user as a command to run, not attempted locally.
- Write tests that pass without network, DB, or containers. That is the only
  automated safety net available on this side.

## Secrets never travel through git

`.env` and `firebase-service-account.json` are gitignored and live only on each
machine. They must be created by hand on the main laptop — they will not appear
after a `git pull`. Both belong at the **repo root** (`D:\Project\agent\`),
because `whatsapp-ai-employee/docker-compose.yml` mounts them from `../`.

## Project summary

Multi-tenant WhatsApp AI automation platform for SMEs ("AI employee").
One codebase, many tenants; per-client behaviour comes from tenant config and
uploaded data, never from forked code.

- Pilot vertical: **hair care seller** (real SKUs, real stock, predictable
  replenishment). Prohibited-claims guardrail is load-bearing — WhatsApp bans
  messaging about medical/healthcare products, so therapeutic language can get
  a client's number banned.
- Stack: Python + FastAPI, PostgreSQL, Qdrant, Redis, Gemini Flash, Next.js
  (admin, not built yet), Firebase auth, Docker Compose.
- Plans: **Basic** = no LLM router, templated replies, escalates to human when
  unsure. **Pro** = LLM router, consultative selling, composed replies.
  The tier rule: when nothing is confident, Basic hands to the human, Pro hands
  to the LLM.
- Phase 1 is complete (see `whatsapp-ai-employee/README.md`). Phase 2 = payments
  + cart messages. Phase 3 = schedulers + admin panel.

## Design rules not to break

1. **Cache facts, not conversations.** Retrieval is cached; composed sales
   replies never are. Advisory questions ("which is better for dry hair") are
   blocked from every fast path regardless of keyword match.
2. **Conversation order is free; transaction order is not.** The AI may raise
   add-ons any time, but cannot create an order without stock, address and
   payment method.
3. **Grounded, not generative.** Replies come only from the tenant's retrieved
   data. Nothing relevant retrieved → escalate, never improvise.
4. **Safety escalations are never tier-gated.** Adverse reactions, medical
   questions and complaints always go to a human.
5. **One codebase.** No per-client forks. Client differences are config, data,
   and event-bus subscribers.

## Reference docs in this repo

- `ai-employee-platform-spec.md` — full spec, packages, 10-phase roadmap, risks
- `credentials-setup-checklist.md` — how to obtain every credential
- `SETUP-MAIN-PC.md` — what to install and run on the main laptop
- `whatsapp-ai-employee/README.md` — architecture, commands, known gaps
