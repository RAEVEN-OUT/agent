import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """One client business. Everything else is scoped to a tenant."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    vertical: Mapped[str] = mapped_column(String(50), default="haircare")

    # "basic" | "pro"  -> drives the cascade behaviour (see orchestrator)
    plan: Mapped[str] = mapped_column(String(20), default="pro")

    # Inbound webhooks carry phone_number_id; that is how we resolve the tenant.
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner_wa_id: Mapped[str | None] = mapped_column(String(30), nullable=True)

    currency: Mapped[str] = mapped_column(String(10), default="INR")

    # Free-form per-tenant behaviour config: welcome_message, tone, bot_name,
    # escalation rules, lead times, etc. Uploaded via the admin panel.
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    customers: Mapped[list["Customer"]] = relationship(back_populates="tenant")

    @property
    def is_pro(self) -> bool:
        return self.plan == "pro"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "wa_id", name="uq_customer_tenant_wa"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    wa_id: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Vertical-specific memory (hair type, concern, preferred size...).
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)

    opted_in: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Used to know whether the free 24h service window is open.
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped[Tenant] = relationship(back_populates="customers")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)

    # "open" | "escalated" | "closed"
    status: Mapped[str] = mapped_column(String(20), default="open")
    # When true the bot stays silent: a human owns this thread.
    human_handoff: Mapped[bool] = mapped_column(Boolean, default=False)

    # Slot-filling state for multi-turn flows (order capture, consultation).
    state: Mapped[dict] = mapped_column(JSONB, default=dict)

    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)

    # WhatsApp message id (wamid). Unique so replayed webhooks cannot double-process.
    wamid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    direction: Mapped[str] = mapped_column(String(10))  # "in" | "out"
    msg_type: Mapped[str] = mapped_column(String(20), default="text")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    handled_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
        Index("ix_product_tenant_active", "tenant_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    sku: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)

    # hair_type / concern / ingredients — used for consultation matching.
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )

    order_number: Mapped[str] = mapped_column(String(30), unique=True)
    # pending -> confirmed -> packed -> shipped -> delivered / cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # unpaid | paid | cod_pending | failed
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_link: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list] = mapped_column(JSONB, default=list)
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    address: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)

    # adverse_reaction | medical | complaint | human_request | low_confidence | guardrail
    reason: Mapped[str] = mapped_column(String(40), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Lead(Base):
    """A qualified enquiry, for businesses where the bot does not close the sale.

    Real estate, interiors, B2B, custom services: the bot's job is to qualify and
    hand over, not to take payment. Success is a good lead, not an order.
    """

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )

    requirement: Mapped[str] = mapped_column(Text)
    budget: Mapped[str | None] = mapped_column(String(80), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # new -> contacted -> qualified -> won / lost
    status: Mapped[str] = mapped_column(String(20), default="new")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageLog(Base):
    """Per-tenant cost metering. Needed from day one to know margin per client."""

    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # llm | embedding | whatsapp_out
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    units: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
