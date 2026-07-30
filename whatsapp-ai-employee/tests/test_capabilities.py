"""Capability kits — the mechanism that makes one codebase serve many verticals.

The claim under test: a new business type is a *tool set*, not new conversation
code. If a salon ever needs `place_order` hand-written for it, this abstraction
has failed.
"""

from app.agent import tools as agent_tools
from app.agent.capabilities import (
    ALWAYS_ON,
    CAPABILITY_TOOLS,
    KITS,
    Capability,
    allowed_tools,
    kit_for,
    prompt_additions,
)


class FakeTenant:
    def __init__(self, settings=None):
        self.settings = settings or {}


class TestKitResolution:
    def test_default_when_unconfigured(self):
        assert kit_for(FakeTenant()) == KITS["consultative_seller"]

    def test_named_kit(self):
        assert kit_for(FakeTenant({"kit": "service_provider"})) == KITS["service_provider"]

    def test_explicit_capability_list_overrides_kit(self):
        tenant = FakeTenant({"kit": "single_product", "capabilities": ["catalog", "booking"]})
        assert set(kit_for(tenant)) == {Capability.CATALOG, Capability.BOOKING}

    def test_unknown_kit_falls_back_to_default(self):
        assert kit_for(FakeTenant({"kit": "nonsense"})) == KITS["consultative_seller"]

    def test_garbage_capability_names_are_ignored(self):
        tenant = FakeTenant({"capabilities": ["catalog", "not_a_capability"]})
        assert set(kit_for(tenant)) == {Capability.CATALOG}


class TestToolExposure:
    def test_single_product_seller_gets_no_catalog_search(self):
        """One SKU — nothing to search. Fewer tools, fewer wrong turns."""
        tools = allowed_tools(FakeTenant({"kit": "single_product"}))
        assert "search_catalog" not in tools
        assert "place_order" in tools

    def test_service_provider_cannot_place_product_orders(self):
        tools = allowed_tools(FakeTenant({"kit": "service_provider"}))
        assert "place_order" not in tools
        assert "check_availability" in tools

    def test_consultative_seller_gets_catalog_and_ordering(self):
        tools = allowed_tools(FakeTenant({"kit": "consultative_seller"}))
        assert {"search_catalog", "save_order_details", "place_order"} <= tools

    def test_salon_with_retail_gets_both(self):
        tools = allowed_tools(FakeTenant({"kit": "service_and_retail"}))
        assert "book_appointment" in tools
        assert "place_order" in tools

    def test_escalation_is_always_available(self):
        for kit in KITS:
            assert "escalate_to_human" in allowed_tools(FakeTenant({"kit": kit})), kit

    def test_always_on_is_not_empty(self):
        assert ALWAYS_ON


class TestSchemaConsistency:
    def test_every_capability_maps_to_tools(self):
        for capability in Capability:
            assert capability in CAPABILITY_TOOLS

    def test_built_tools_exist_in_the_registry(self):
        """Booking tools are declared but not implemented yet — flag the gap
        explicitly rather than discovering it when a salon signs up."""
        implemented = set(agent_tools.IMPLEMENTATIONS)
        not_yet = set()
        for capability, names in CAPABILITY_TOOLS.items():
            for name in names:
                if name not in implemented:
                    not_yet.add(name)
        assert not_yet == {"check_availability", "book_appointment"}, (
            f"unexpected unimplemented tools: {not_yet}"
        )

    def test_non_booking_kits_only_use_implemented_tools(self):
        implemented = set(agent_tools.IMPLEMENTATIONS)
        for kit_name, caps in KITS.items():
            if Capability.BOOKING in caps:
                continue
            for name in allowed_tools(FakeTenant({"kit": kit_name})):
                assert name in implemented, f"{kit_name} needs unbuilt tool {name}"


class TestPromptGuidance:
    def test_consultative_kit_explains_advice_selling(self):
        text = prompt_additions(FakeTenant({"kit": "consultative_seller"})).lower()
        assert "advice" in text or "recommend" in text

    def test_booking_kit_forbids_inventing_slots(self):
        text = prompt_additions(FakeTenant({"kit": "service_provider"})).lower()
        assert "never invent" in text

    def test_single_product_kit_still_gets_ordering_guidance(self):
        text = prompt_additions(FakeTenant({"kit": "single_product"})).lower()
        assert "summary" in text or "explicit yes" in text
