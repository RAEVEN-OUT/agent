from app.modules.order_capture import (
    REQUIRED_SLOTS,
    _order_number,
    _parse_payment_method,
    _parse_pincode,
    _parse_quantity,
)


class TestQuantityParsing:
    def test_valid_numbers(self):
        assert _parse_quantity("2") == 2
        assert _parse_quantity(3) == 3
        assert _parse_quantity(" 5 ") == 5

    def test_rejects_zero_and_negative(self):
        assert _parse_quantity("0") is None
        assert _parse_quantity("-1") is None

    def test_rejects_absurd_quantities(self):
        assert _parse_quantity("500") is None

    def test_rejects_non_numeric(self):
        assert _parse_quantity("two") is None
        assert _parse_quantity("") is None
        assert _parse_quantity(None) is None


class TestPaymentMethodParsing:
    def test_cod_variants(self):
        for text in ("cod", "COD please", "cash on delivery", "cash"):
            assert _parse_payment_method(text) == "cod"

    def test_online_variants(self):
        for text in ("online", "UPI", "card", "pay now", "gpay", "phonepe"):
            assert _parse_payment_method(text) == "online"

    def test_unclear_returns_none(self):
        assert _parse_payment_method("whatever is fine") is None


class TestPincodeParsing:
    def test_valid_pincode(self):
        assert _parse_pincode("641002") == "641002"
        assert _parse_pincode("pincode is 641 002") == "641002"

    def test_wrong_length_rejected(self):
        assert _parse_pincode("12345") is None
        assert _parse_pincode("1234567") is None
        assert _parse_pincode("no digits here") is None


class TestOrderNumber:
    def test_format_and_uniqueness(self):
        numbers = {_order_number() for _ in range(50)}
        assert len(numbers) > 45  # random suffix, collisions should be rare
        for number in numbers:
            assert number.startswith("ORD")
            assert len(number) == 13


class TestRequiredSlots:
    def test_address_fields_are_required_before_order_creation(self):
        # Guards the business precondition: no order without deliverability.
        for slot in ("product", "quantity", "name", "address", "pincode", "payment_method"):
            assert slot in REQUIRED_SLOTS
