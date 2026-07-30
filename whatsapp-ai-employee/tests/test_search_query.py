"""Full-text query construction.

Regression origin: a live conversation where "how much is argan oil" returned
ZERO products. Cause: plainto_tsquery ANDs every term, so the query became
'much & argan & oil' and no product contains the word "much". Conversational
padding therefore broke retrieval almost entirely — "wht products do u sell",
"how much is argan oil" and "is ur shampoo sulfate free" all matched nothing.
"""

from app.modules.retrieval import build_or_tsquery
from app.pipeline.normalize import normalize


def q(text: str) -> str:
    return build_or_tsquery(normalize(text))


class TestFillerRemoval:
    def test_price_question_keeps_only_product_terms(self):
        assert q("how much is argan oil") == "argan | oil"

    def test_stock_question(self):
        # "you"/"do"/"have" are filler; "shampoo" is the signal.
        assert q("do u have shampoo") == "shampoo"

    def test_catalog_question(self):
        # "sell" survives filtering, which is harmless under OR semantics —
        # it simply matches nothing and contributes no rank.
        assert q("wht products do u sell") == "products | sell"

    def test_no_bare_and_semantics(self):
        """The actual bug: every term ANDed meant one filler word killed it."""
        for text in ("how much is argan oil", "do you have any conditioner"):
            assert "&" not in q(text)
            assert "|" in q(text) or q(text)


class TestTokenHandling:
    def test_dedupes(self):
        assert q("oil oil oil") == "oil"

    def test_drops_short_tokens(self):
        assert "ml" not in q("200 ml oil")

    def test_keeps_numbers_of_length_three_plus(self):
        assert "200" in q("200 ml oil")

    def test_strips_punctuation(self):
        assert q("price?") == "price"

    def test_empty_input(self):
        assert build_or_tsquery("") == ""

    def test_only_filler_returns_empty(self):
        # Must return "" so the caller skips the query rather than sending
        # invalid tsquery syntax to Postgres.
        assert build_or_tsquery("how much is it") == ""

    def test_no_dangling_operators(self):
        for text in ("oil", "how much", "the a an"):
            result = build_or_tsquery(text)
            assert not result.startswith("|")
            assert not result.endswith("|")


class TestSpellingVariants:
    def test_sulfate_normalises_to_catalog_spelling(self):
        """Catalog says 'sulphate'; customers type 'sulfate'."""
        assert "sulphate" in q("is ur shampoo sulfate free")

    def test_color_variant(self):
        assert "colour" in q("colored hair")


class TestRealFailedMessages:
    """Exact messages that returned nothing in production."""

    def test_all_produce_usable_queries(self):
        for text in (
            "wht products do u sell",
            "how much is argan oil",
            "is ur shampoo sulfate free",
            "do u have shampoo for dandruff",
            "I want to order ur oil",
        ):
            result = q(text)
            assert result, f"{text!r} produced an empty query"
