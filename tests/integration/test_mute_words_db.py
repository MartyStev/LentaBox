import pytest

import config
import db.mute_words as mute_words

pytestmark = pytest.mark.integration


def test_add_list_remove_roundtrip(db):
    assert mute_words.list_words() == []
    assert mute_words.add("  Курс   Доллара ") == "added"
    assert mute_words.add("курс доллара") == "exists"              # normalised, case-insensitive
    assert mute_words.add("футбол") == "added"
    assert mute_words.list_words() == ["курс доллара", "футбол"]
    assert mute_words.remove("ФУТБОЛ") is True
    assert mute_words.remove("футбол") is False
    assert mute_words.list_words() == ["курс доллара"]


def test_invalid_words_and_the_limit(db, monkeypatch):
    assert mute_words.add("a") == "invalid"
    assert mute_words.add("") == "invalid"
    monkeypatch.setattr(config, "MUTE_WORDS_LIMIT", 2)
    assert mute_words.add("one") == "added"
    assert mute_words.add("two") == "added"
    assert mute_words.add("three") == "limit"
    assert mute_words.add("two") == "exists"                        # a duplicate is not a limit hit
    assert mute_words.remove("not-there") is False
