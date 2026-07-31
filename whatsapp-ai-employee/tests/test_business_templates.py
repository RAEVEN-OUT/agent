"""Business templates — the productised unit sold to clients.

The critical assertion: **success is not the same in every template.** An enquiry
business must never quote a price; a consultancy business should close the order.
A bot that tries to close a sale for an interior designer is behaving wrongly,
not just sub-optimally.
"""

from app.agent import tools as agent_tools
from app.agent.business_templates import (
    DEFAULT_TEMPLATE,
    TEMPLATES,
    Capability,
    for_tenant,
    get,
    onboarding_checklist,
)
from app.agent.capabilities import allowed_tools


class FakeTenant:
    def __init__(self, settings=None):
        self.settings = settings or {}


class TestTemplateCompleteness:
    def test_all_expected_templates_exist(self):
        for key in ("consultancy", "single_product", "enquiry", "catalog", "made_to_order"):
            assert key in TEMPLATES

    def test_every_template_declares_a_goal(self):
        for key, template in TEMPLATES.items():
            assert template.goal.strip(), key

    def test_every_template_has_catalog_fields(self):
        for key, template in TEMPLATES.items():
            assert template.catalog_fields, key

    def test_every_template_has_policy_questions(self):
        """These become the FAQ rows the client fills in — the onboarding form."""
        for key, template in TEMPLATES.items():
            assert template.policy_questions, key

    def test_every_template_has_outbound_message_templates(self):
        """Pre-written WhatsApp templates are the reusable leverage per vertical."""
        for key, template in TEMPLATES.items():
            assert template.message_templates, key

    def test_message_templates_are_valid_for_submission(self):
        for key, template in TEMPLATES.items():
            for msg in template.message_templates:
                assert msg.category in ("UTILITY", "MARKETING"), f"{key}.{msg.name}"
                assert "{{1}}" in msg.body, f"{key}.{msg.name} has no variable"
                # Marketing templates need an opt-out to protect the number's
                # quality rating.
                if msg.category == "MARKETING":
                    assert "STOP" in msg.body, f"{key}.{msg.name} lacks an opt-out"


class TestEnquiryTemplateNeverSells:
    """The highest-stakes rule: quoting is the human's job here."""

    def test_enquiry_cannot_place_orders(self):
        tools = allowed_tools(FakeTenant({"template": "enquiry"}))
        assert "place_order" not in tools
        assert "save_order_details" not in tools
        assert "capture_enquiry" in tools

    def test_enquiry_has_no_catalog_search(self):
        """No catalog means no prices to accidentally quote."""
        tools = allowed_tools(FakeTenant({"template": "enquiry"}))
        assert "search_catalog" not in tools

    def test_enquiry_goal_forbids_quoting(self):
        assert "never quote" in TEMPLATES["enquiry"].goal.lower()

    def test_enquiry_prompt_forbids_prices(self):
        prompt = TEMPLATES["enquiry"].extra_prompt.lower()
        assert "do not quote" in prompt or "never state a price" in prompt


class TestSingleProductTemplate:
    def test_no_catalog_search(self):
        tools = allowed_tools(FakeTenant({"template": "single_product"}))
        assert "search_catalog" not in tools
        assert "place_order" in tools

    def test_prompt_says_never_ask_which_product(self):
        assert "never ask which product" in TEMPLATES["single_product"].extra_prompt.lower()


class TestConsultancyTemplate:
    def test_has_intake_questions(self):
        assert TEMPLATES["consultancy"].intake

    def test_can_search_and_order(self):
        tools = allowed_tools(FakeTenant({"template": "consultancy"}))
        assert {"search_catalog", "place_order"} <= tools

    def test_has_a_refill_template(self):
        names = {m.name for m in TEMPLATES["consultancy"].message_templates}
        assert "refill_reminder" in names


class TestMadeToOrderTemplate:
    def test_lead_time_is_in_the_catalog_schema(self):
        assert any("lead_time" in f for f in TEMPLATES["made_to_order"].catalog_fields)

    def test_prompt_prioritises_lead_time_over_stock(self):
        assert "lead time" in TEMPLATES["made_to_order"].extra_prompt.lower()


class TestResolution:
    def test_unknown_template_falls_back(self):
        assert get("nonsense").key == DEFAULT_TEMPLATE

    def test_tenant_without_config_gets_default(self):
        assert for_tenant(FakeTenant()).key == DEFAULT_TEMPLATE

    def test_template_drives_capabilities(self):
        assert Capability.ENQUIRY in for_tenant(FakeTenant({"template": "enquiry"})).capabilities

    def test_all_tools_used_by_templates_are_implemented(self):
        implemented = set(agent_tools.IMPLEMENTATIONS)
        for key in TEMPLATES:
            for name in allowed_tools(FakeTenant({"template": key})):
                assert name in implemented, f"template {key} needs unbuilt tool {name}"


class TestOnboardingChecklist:
    def test_lists_catalog_columns(self):
        items = "\n".join(onboarding_checklist("consultancy"))
        assert "sku" in items and "price" in items

    def test_lists_policy_questions(self):
        items = "\n".join(onboarding_checklist("catalog"))
        assert "delivery charges" in items.lower()

    def test_mentions_whatsapp_verification(self):
        items = "\n".join(onboarding_checklist("enquiry")).lower()
        assert "verification" in items
