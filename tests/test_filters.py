import pytest

import config
from core import filters


def test_matches_is_case_insensitive_and_substring_based():
    assert filters.matches("Курс ДОЛЛАРА вырос", ["доллар"])
    assert filters.matches("Футбольный матч", ["футбол"])
    assert not filters.matches("Курс рубля", ["доллар"])


def test_matches_ignores_empty_inputs():
    assert not filters.matches("", ["a"])
    assert not filters.matches("text", [])
    assert not filters.matches("text", None)
    assert not filters.matches("text", [""])


def test_normalize_word_trims_lowercases_and_collapses_spaces():
    assert filters.normalize_word("  Курс   Доллара ") == "курс доллара"


@pytest.mark.parametrize("word", ["", "   ", "a", "x" * (config.MUTE_WORD_MAX + 1), None])
def test_normalize_word_rejects_too_short_too_long_and_empty(word):
    assert filters.normalize_word(word) is None
