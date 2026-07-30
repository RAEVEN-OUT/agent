"""Tool contract tests — the load-bearing safety layer in agent mode.

The model is allowed to decide *what to do*. It is not allowed to decide prices,
totals, delivery dates, or whether an order is valid. Those live in the tools, so
a wrong tool sequence is harmless. These tests pin that boundary.
"""

import inspect

from app.agent import tools


class TestSchemaHygiene:
    def test_every_declared_tool_has_an_implementation(self):
        declared = {s["name"] for s in tools.TOOL_SCHEMAS}
        implemented = set(tools.IMPLEMENTATIONS)
        assert declared == implemented, declared ^ implemented

    def test_every_tool_has_a_useful_description(self):
        for schema in tools.TOOL_SCHEMAS:
            # The description is the model's only documentation — it is behaviour.
            assert len(schema["description"]) > 60, schema["name"]

    def test_parameters_are_valid_json_schema(self):
        for schema in tools.TOOL_SCHEMAS:
            params = schema["parameters"]
            assert params["type"] == "object"
            assert isinstance(params.get("properties", {}), dict)
            for name in params.get("required", []):
                assert name in params["properties"], f"{schema['name']}.{name}"

    def test_all_implementations_are_async(self):
        for name, impl in tools.IMPLEMENTATIONS.items():
            assert inspect.iscoroutinefunction(impl), name


class TestDangerousCapabilitiesAreNotExposed:
    """What the model must never be able to do directly."""

    def test_no_discount_tool(self):
        names = {s["name"] for s in tools.TOOL_SCHEMAS}
        for forbidden in ("apply_discount", "set_price", "override_price", "give_discount"):
            assert forbidden not in names

    def test_no_tool_accepts_a_price(self):
        """If the model could pass a price, prompt injection could set it."""
        for schema in tools.TOOL_SCHEMAS:
            for param in schema["parameters"].get("properties", {}):
                assert param not in ("price", "total", "unit_price", "amount", "discount"), (
                    f"{schema['name']} accepts {param} — prices must come from the catalog"
                )

    def test_no_tool_accepts_a_delivery_date(self):
        for schema in tools.TOOL_SCHEMAS:
            for param in schema["parameters"].get("properties", {}):
                assert "date" not in param.lower(), f"{schema['name']}.{param}"

    def test_place_order_takes_no_arguments(self):
        """It must read the validated draft, not accept whatever the model invents."""
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "place_order")
        assert schema["parameters"].get("properties", {}) == {}


class TestOrderValidationContract:
    def test_required_fields_include_deliverability(self):
        for field in ("sku", "quantity", "customer_name", "address", "pincode", "payment_method"):
            assert field in tools.REQUIRED

    def test_sku_is_required_not_free_text_product_name(self):
        """A name can be ambiguous between variants; a SKU cannot."""
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "save_order_details")
        props = schema["parameters"]["properties"]
        assert "sku" in props
        assert "product_name" not in props

    def test_payment_method_is_constrained(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "save_order_details")
        assert set(schema["parameters"]["properties"]["payment_method"]["enum"]) == {"cod", "online"}

    def test_escalation_reasons_are_constrained(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "escalate_to_human")
        reasons = set(schema["parameters"]["properties"]["reason"]["enum"])
        assert {"human_request", "complaint", "medical"} <= reasons


class TestToolDispatch:
    async def test_unknown_tool_returns_error_not_exception(self):
        result = await tools.execute("nonexistent_tool", {}, ctx=None)
        assert "error" in result

    async def test_bad_arguments_return_error_not_exception(self):
        result = await tools.execute("search_catalog", {"wrong_arg": 1}, ctx=None)
        assert "error" in result


class TestPromptGuidance:
    """Descriptions must actively steer away from the bugs we hit."""

    def test_catalog_warns_against_choosing_a_variant(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "search_catalog")
        text = schema["description"].lower()
        assert "ask" in text and "variant" in text

    def test_catalog_forbids_invented_prices(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "search_catalog")
        assert "never state a price" in schema["description"].lower()

    def test_review_forbids_self_calculated_totals(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "review_order")
        assert "never calculate" in schema["description"].lower()

    def test_escalation_forbids_guessing(self):
        schema = next(s for s in tools.TOOL_SCHEMAS if s["name"] == "escalate_to_human")
        assert "never guess" in schema["description"].lower()
