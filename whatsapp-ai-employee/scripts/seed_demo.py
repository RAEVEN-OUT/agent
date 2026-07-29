"""Seed the pilot tenant: a hair care seller, with catalog + FAQs.

Run:  docker compose exec api python -m scripts.seed_demo

Idempotent — safe to re-run. It also pushes catalog/FAQ text into Qdrant so
semantic search has something to find.
"""

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Faq, Product, Tenant
from app.db.session import SessionLocal, init_models
from app.services.llm_service import llm_service
from app.services.qdrant_service import qdrant_service

TENANT_SLUG = "glow-roots"

PRODUCTS = [
    {
        "sku": "ARG-OIL-100",
        "name": "Argan Repair Hair Oil",
        "description": "Lightweight argan and almond oil blend for dry, frizzy hair. Use twice a week before washing.",
        "size": "100 ml",
        "price": 449,
        "stock": 40,
        "attributes": {"hair_type": ["dry", "frizzy"], "concern": ["dryness", "frizz"]},
    },
    {
        "sku": "ARG-OIL-200",
        "name": "Argan Repair Hair Oil",
        "description": "Lightweight argan and almond oil blend for dry, frizzy hair. Value size.",
        "size": "200 ml",
        "price": 799,
        "stock": 25,
        "attributes": {"hair_type": ["dry", "frizzy"], "concern": ["dryness", "frizz"]},
    },
    {
        "sku": "ROSE-SHM-200",
        "name": "Rosemary Strengthening Shampoo",
        "description": "Sulphate-free shampoo with rosemary and biotin, formulated for thinning and weak hair.",
        "size": "200 ml",
        "price": 549,
        "stock": 30,
        "attributes": {"hair_type": ["normal", "oily"], "concern": ["hair fall", "thinning"]},
    },
    {
        "sku": "ROSE-CON-200",
        "name": "Rosemary Strengthening Conditioner",
        "description": "Pairs with the rosemary shampoo. Adds slip and reduces breakage while combing.",
        "size": "200 ml",
        "price": 549,
        "stock": 28,
        "attributes": {"hair_type": ["normal", "dry"], "concern": ["breakage"]},
    },
    {
        "sku": "TEA-SHM-200",
        "name": "Tea Tree Clarifying Shampoo",
        "description": "Tea tree and salicylic shampoo formulated for oily scalp and flaking.",
        "size": "200 ml",
        "price": 499,
        "stock": 22,
        "attributes": {"hair_type": ["oily"], "concern": ["dandruff", "flaking", "oily scalp"]},
    },
    {
        "sku": "CURL-CRM-150",
        "name": "Curl Define Cream",
        "description": "Leave-in cream for wavy and curly hair. Defines curls without crunch.",
        "size": "150 ml",
        "price": 649,
        "stock": 15,
        "attributes": {"hair_type": ["curly", "wavy"], "concern": ["frizz", "definition"]},
    },
    {
        "sku": "SILK-SRM-050",
        "name": "Silk Finish Hair Serum",
        "description": "Heat-protectant serum with silicone-free smoothing agents. Use before styling.",
        "size": "50 ml",
        "price": 399,
        "stock": 0,
        "attributes": {"hair_type": ["all"], "concern": ["frizz", "heat damage"]},
    },
    {
        "sku": "COMBO-ROSE",
        "name": "Rosemary Duo Combo (Shampoo + Conditioner)",
        "description": "The rosemary shampoo and conditioner together at a bundle price.",
        "size": "200 ml x 2",
        "price": 999,
        "stock": 18,
        "attributes": {"concern": ["hair fall", "breakage"], "bundle": True},
    },
]

FAQS = [
    {
        "question": "What are the delivery charges?",
        "answer": "Delivery is free on orders above INR 599. Below that it is INR 49 anywhere in India.",
    },
    {
        "question": "How long does delivery take?",
        "answer": "Metro cities usually get it in 2-3 working days, and the rest of India in 4-6 working days.",
    },
    {
        "question": "Do you offer cash on delivery?",
        "answer": "Yes, cash on delivery is available for orders up to INR 2000. Above that we ask for prepaid.",
    },
    {
        "question": "What is your return policy?",
        "answer": "Unopened products can be returned within 7 days of delivery. Opened bottles cannot be returned for hygiene reasons.",
    },
    {
        "question": "Are your products vegan and cruelty free?",
        "answer": "Yes, all our products are vegan and never tested on animals.",
    },
    {
        "question": "Are the products sulphate and paraben free?",
        "answer": "Our shampoos are sulphate-free, and every product in the range is paraben-free.",
    },
    {
        "question": "What are your working hours?",
        "answer": "We reply to messages between 10am and 7pm, Monday to Saturday.",
    },
]

TENANT_SETTINGS = {
    "business_name": "Glow Roots",
    "bot_name": "Roo",
    "tone": "warm, friendly, concise — like a knowledgeable shop assistant",
    # Delivery promises must come from config, never from a model that could
    # invent a date. Used in the order summary and confirmation.
    "delivery_days_default": 5,
    "delivery_days_metro": 3,
    "metro_pincode_prefixes": ["11", "40", "56", "60", "70", "50", "38", "41"],
    "cta": "Would you like to place an order?",
    "welcome_message": "Hi! Welcome to Glow Roots 🌿 How can I help you today?",
    "farewell_message": "Thank you for shopping with Glow Roots!",
    "fallback_message": "Let me check that with our team and get back to you shortly.",
    "intake": [
        {"slot": "hair_type", "question": "Is your hair oily, dry, normal or curly?"},
        {
            "slot": "concern",
            "question": "What would you like to work on — hair fall, dandruff, frizz or dryness?",
        },
        {"slot": "budget", "question": "Any budget you'd like me to stay within?"},
    ],
}


async def seed() -> None:
    await init_models()
    await qdrant_service.ensure_collection()

    async with SessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        tenant = result.scalar_one_or_none()

        if not tenant:
            tenant = Tenant(
                name="Glow Roots Hair Care",
                slug=TENANT_SLUG,
                vertical="haircare",
                plan="pro",
                whatsapp_phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID or "TEST_PHONE_ID",
                whatsapp_business_account_id=settings.WHATSAPP_BUSINESS_ACCOUNT_ID or None,
                currency="INR",
                settings=TENANT_SETTINGS,
            )
            db.add(tenant)
            await db.flush()
            print(f"created tenant {tenant.slug} ({tenant.id})")
        else:
            tenant.whatsapp_phone_number_id = (
                settings.WHATSAPP_PHONE_NUMBER_ID or tenant.whatsapp_phone_number_id
            )
            tenant.settings = TENANT_SETTINGS
            print(f"tenant {tenant.slug} already exists — refreshed settings")

        # --- products ---
        for item in PRODUCTS:
            existing = await db.execute(
                select(Product).where(
                    Product.tenant_id == tenant.id, Product.sku == item["sku"]
                )
            )
            product = existing.scalar_one_or_none()
            if product:
                for key, value in item.items():
                    setattr(product, key, value)
            else:
                db.add(Product(tenant_id=tenant.id, **item))

        # --- faqs ---
        for item in FAQS:
            existing = await db.execute(
                select(Faq).where(
                    Faq.tenant_id == tenant.id, Faq.question == item["question"]
                )
            )
            if not existing.scalar_one_or_none():
                db.add(Faq(tenant_id=tenant.id, **item))

        await db.commit()
        print(f"seeded {len(PRODUCTS)} products and {len(FAQS)} FAQs")

        # --- index into Qdrant for semantic fallback ---
        if not llm_service.available:
            print("GEMINI_API_KEY not set — skipping vector indexing")
            return

        tenant_id = str(tenant.id)
        indexed = 0
        for item in PRODUCTS:
            text = (
                f"{item['name']} ({item['size']}) - INR {item['price']}. "
                f"{item['description']}"
            )
            try:
                vector = await llm_service.embed(text)
                await qdrant_service.delete_by_source(tenant_id, item["sku"])
                await qdrant_service.upsert(
                    tenant_id, "product", item["sku"], text, vector,
                    {"sku": item["sku"], "name": item["name"]},
                )
                indexed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! failed to index {item['sku']}: {exc}")

        for item in FAQS:
            text = f"{item['question']} {item['answer']}"
            try:
                vector = await llm_service.embed(text)
                await qdrant_service.delete_by_source(tenant_id, item["question"][:60])
                # Store the answer in the payload so a Basic-plan tenant can
                # return it verbatim without an LLM composing anything.
                await qdrant_service.upsert(
                    tenant_id,
                    "faq",
                    item["question"][:60],
                    text,
                    vector,
                    {"question": item["question"], "answer": item["answer"]},
                )
                indexed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! failed to index FAQ: {exc}")

        print(f"indexed {indexed} chunks into Qdrant")


if __name__ == "__main__":
    asyncio.run(seed())
