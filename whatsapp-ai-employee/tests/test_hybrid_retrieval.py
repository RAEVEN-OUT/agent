"""Retrieval confidence and exact-value guarding.

Why lexical search survives the move to semantic-primary: embeddings cannot
reliably tell "100 ml" from "200 ml", or ARG-OIL-100 from ARG-OIL-200. Those
embed at cosine > 0.95. Quoting the wrong variant is not a near miss — it is a
wrong price and a wrong shipment.
"""

from app.core.config import settings
from app.modules.hybrid_retrieval import Confidence, _classify, find_exact_terms


class TestExactTermDetection:
    def test_finds_sizes(self):
        assert "200 ml" in find_exact_terms("do you have the 200 ml")
        assert "100 ml" in find_exact_terms("how much is the 100ml oil")

    def test_finds_sku(self):
        assert "ARG-OIL-200" in find_exact_terms("PRODUCT: ARG-OIL-200")

    def test_finds_order_number(self):
        assert "ORD2607308JWX" in find_exact_terms("what about ORD2607308JWX")

    def test_ignores_ordinary_text(self):
        assert find_exact_terms("which shampoo is good for dandruff") == []

    def test_handles_empty(self):
        assert find_exact_terms("") == []
        assert find_exact_terms(None) == []

    def test_distinguishes_variants(self):
        """The whole reason lexical search is kept."""
        assert find_exact_terms("200ml") != find_exact_terms("100ml")


class TestConfidenceClassification:
    def test_exact_match_wins_outright(self):
        assert _classify(0.10, 0.0, has_exact=True) is Confidence.EXACT

    def test_clear_winner_is_high(self):
        result = _classify(
            settings.RETRIEVAL_HIGH + 0.05,
            settings.RETRIEVAL_MIN_GAP + 0.05,
            has_exact=False,
        )
        assert result is Confidence.HIGH

    def test_strong_but_tied_is_ambiguous(self):
        """Two documents fitting equally well means ask, not guess."""
        result = _classify(settings.RETRIEVAL_HIGH + 0.05, 0.001, has_exact=False)
        assert result is Confidence.AMBIGUOUS

    def test_below_floor_is_none(self):
        result = _classify(settings.RETRIEVAL_FLOOR - 0.05, 0.5, has_exact=False)
        assert result is Confidence.NONE

    def test_middling_is_low(self):
        mid = (settings.RETRIEVAL_FLOOR + settings.RETRIEVAL_HIGH) / 2
        assert _classify(mid, 0.02, has_exact=False) is Confidence.LOW

    def test_thresholds_are_ordered_sanely(self):
        assert 0 < settings.RETRIEVAL_FLOOR < settings.RETRIEVAL_HIGH <= 1.0
        assert 0 < settings.RETRIEVAL_MIN_GAP < 0.5

    def test_none_confidence_never_answers(self):
        """NONE must mean escalate — never improvise from general knowledge."""
        assert _classify(0.0, 0.0, has_exact=False) is Confidence.NONE
