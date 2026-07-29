"""Tests for the pure decision logic in catalog_qa.

The advisory/factual split is what stops the cost cascade from making the bot
worse at selling: advisory questions must never be answered from a cache or a
template, because that is where the sales judgement lives.
"""

from app.modules.catalog_qa import _templated_product_reply, is_advisory, is_factual
from app.modules.retrieval import ProductHit
from app.pipeline.normalize import normalize


def hit(name="Argan Repair Hair Oil", price=449.0, stock=10, size="100 ml"):
    return ProductHit(
        id="1", sku="ARG-OIL-100", name=name, description="", size=size,
        price=price, stock=stock, attributes={}, rank=0.5,
    )


class TestIsAdvisory:
    def test_comparative_questions_are_advisory(self):
        for text in (
            "which shampoo is better for dry hair",
            "what should i use for dandruff",
            "can you suggest something",
            "recommend a good oil",
            "argan oil vs serum",
            "which is best for frizz",
            "is this suitable for curly hair",
            "help me choose",
        ):
            assert is_advisory(normalize(text)), text

    def test_factual_questions_are_not_advisory(self):
        for text in (
            "how much is the argan oil",
            "do you have 200ml",
            "what are the delivery charges",
            "is the tea tree shampoo in stock",
        ):
            assert not is_advisory(normalize(text)), text


class TestIsFactual:
    def test_policy_questions_are_factual(self):
        assert is_factual(normalize("what are the delivery charges"))
        assert is_factual(normalize("what is your return policy"))
        assert is_factual(normalize("is cod available"))

    def test_product_advice_is_not_factual(self):
        assert not is_factual(normalize("which one suits dry hair"))


class TestTemplatedReply:
    def test_single_in_stock_product_invites_order(self):
        reply = _templated_product_reply([hit()], "INR")
        assert "449" in reply
        assert "in stock" in reply
        assert "order" in reply.lower()

    def test_out_of_stock_is_stated_clearly(self):
        reply = _templated_product_reply([hit(stock=0)], "INR")
        assert "out of stock" in reply

    def test_multiple_products_are_listed(self):
        reply = _templated_product_reply(
            [hit(), hit(name="Rosemary Shampoo", price=549.0, size="200 ml")], "INR"
        )
        assert "449" in reply and "549" in reply
        assert reply.count("•") == 2

    def test_template_never_contains_prohibited_claims(self):
        from app.pipeline.guardrails import scan_outbound

        reply = _templated_product_reply([hit()], "INR")
        assert scan_outbound(reply) == []
