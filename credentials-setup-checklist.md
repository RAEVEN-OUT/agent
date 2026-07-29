# Credentials Setup Checklist

Work through these in order. Total time roughly 45–60 minutes.
Meta's and Google's UI labels shift occasionally — if a button name differs slightly, the path is still the same.

**Do not paste secrets into chat.** Put everything into a `.env` file (instructions at the bottom).

---

## 1. WhatsApp Cloud API  (~30–45 min)

### Prerequisites
- A Facebook account (personal is fine — it only owns the developer app)
- Your phone number, still working normally on WhatsApp

### 1a. Create the developer app
1. Go to **developers.facebook.com** → log in → **My Apps** → **Create App**
2. When asked what you're building, choose the **Business** app type
3. Give it a name (e.g. "AI Employee Platform") and continue

### 1b. Add the WhatsApp product
1. On the app dashboard, scroll to **WhatsApp** → click **Set up**
2. You'll be prompted to attach a **Meta Business Account**. If you don't have one, the prompts will walk you through creating it — do that.

This automatically creates, for free:
- A **test WhatsApp Business Account**
- A **test business phone number** (this is the sender — you do *not* supply your own number here)
- A set of **pre-approved templates** including `hello_world`

### 1c. Add your number as a test recipient
1. Left menu → **WhatsApp** → **API Setup**
2. Under *Send and receive messages*, click the **To** field → **Manage phone number list**
3. Add your own WhatsApp number. You'll get a confirmation code in WhatsApp — enter it to verify.
4. Up to 5 recipient numbers can be added this way.

### 1d. Send a test message (confirms it works)
1. Still in **API Setup**: confirm the test number is in **From**, your number in **To**
2. Click **Send message**
3. You should receive the `hello_world` template on your phone. If yes, the API side is working.

### 1e. Grab the IDs
From the **API Setup** panel, copy:
- **Phone Number ID** (the test number's ID, not the phone number itself)
- **WhatsApp Business Account ID** (WABA ID)
- **App ID** (from Settings → Basic)
- **App Secret** (Settings → Basic → click *Show*) — needed to verify webhook signatures

The token shown on this panel is **temporary (expires in ~24 hours)**. Fine for a first test, useless for a running service — so next step creates a permanent one.

### 1f. Create a permanent access token
1. Go to **business.facebook.com** → **Business Settings**
2. Left menu → **Users** → **System Users** → **Add**
3. Name it (e.g. "platform-backend"), role **Admin**, create
4. Click the system user → **Assign Assets** → select your **app** → grant **Manage app** → confirm
5. Reload the page and confirm the app shows as assigned (permissions can take a couple of minutes)
6. Click **Generate token** → select your app → choose an expiration preference (choose *Never* if offered) → tick these three permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
   - `business_management`
7. **Generate** and copy the token immediately — it isn't shown again.

### 1g. Webhook (I'll help with this at Phase 1)
Webhooks need a public HTTPS URL, which your laptop doesn't have. During development we'll use a tunnel (ngrok or similar) and register that URL. You'll need to invent a **verify token** — any random string you make up, e.g. `hc_platform_9f2k4x`. Just write it down; we register the same string on both sides.

### 1h. Later, for going live (not needed now)
Real business number + **Meta business verification** (requires business documents, takes days). Only needed to message real customers, raise messaging limits, and get more template slots. Worth starting early if you have a real launch date, but it does not block development at all.

**Collect from this section:** Phone Number ID, WABA ID, App ID, App Secret, permanent access token, your invented verify token.

---

## 2. Gemini API key  (~2 min)

1. Go to **aistudio.google.com** → sign in with a Google account
2. Click **Get API key** (top of the page or left menu)
3. **Create API key** → select an existing Google Cloud project or let it create one
4. Copy the key

Notes: there's a free tier with rate limits, adequate for development. For production throughput you'll enable billing on the associated Google Cloud project. Same key covers both text generation and embeddings.

**Collect:** the API key.

---

## 3. Firebase  (~10 min)

### 3a. Create the project
1. Go to **console.firebase.google.com** → **Add project**
2. Name it, continue. Google Analytics is optional — skip it.

### 3b. Enable authentication
1. Left menu → **Build** → **Authentication** → **Get started**
2. Under **Sign-in method**, enable **Email/Password** (add **Google** too if you want social login for admins later)

### 3c. Get the web config (for the Next.js panel)
1. **Project settings** (gear icon) → **General**
2. Scroll to *Your apps* → click the **Web** icon `</>`
3. Register the app (nickname only; skip Firebase Hosting)
4. Copy the `firebaseConfig` object shown — `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`

These values are not secret (they ship in the browser bundle), but keep them together.

### 3d. Get the service account key (for the FastAPI backend)
1. **Project settings** → **Service accounts**
2. **Generate new private key** → confirms → downloads a `.json` file
3. This file **is** secret. Save it into the project folder as `firebase-service-account.json`

**Collect:** the `firebaseConfig` values, and the service account JSON file.

---

## 4. Razorpay — Phase 2 only, not needed yet

1. Sign up at **razorpay.com**
2. **Test mode keys are available immediately** without completing KYC — enough for all development
3. Dashboard → **Settings** → **API Keys** → **Generate Test Key** → copy **Key ID** and **Key Secret**
4. For live payments later: complete KYC (PAN, bank account, business proof, GST if applicable), then generate live keys

**Collect (later):** Test Key ID + Test Key Secret.

---

## 5. How to hand these to me

Create a file at `D:\Project\agent\.env` with this content, filling in your values:

```
# WhatsApp
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=
WHATSAPP_APP_ID=
WHATSAPP_APP_SECRET=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_API_VERSION=v24.0

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
GEMINI_EMBEDDING_DIMENSIONS=1536

# Firebase (web config — for Next.js)
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=
FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=
FIREBASE_MESSAGING_SENDER_ID=
FIREBASE_APP_ID=

# Firebase (backend)
FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json

# Razorpay (Phase 2)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```

Then tell me it's ready and I'll read the file directly. Two rules:
- `.env` and `firebase-service-account.json` go into `.gitignore` before any commit — never into version control
- If a token ever leaks (pasted somewhere public, committed by accident), regenerate it rather than hoping; Meta and Google both let you revoke and reissue

---

## Order and dependencies

Nothing here blocks anything else — do them in any order. Practical sequencing:

1. **Gemini key first** (2 minutes, and it unblocks all the AI work)
2. **WhatsApp** next (longest, and Phase 1 is built around it)
3. **Firebase** when we start the admin panel
4. **Razorpay** at Phase 2

I can begin Phase 1 against mock data with none of these — the Gemini key and WhatsApp credentials are what turn it from mock to real.
