import re
import string

import pytest

import config
from core import i18n, runtime
from core.messages import en, ru


@pytest.fixture(autouse=True)
def reset_language():
    yield
    runtime.reset("language")


def placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_catalogs_have_the_same_keys():
    assert set(ru.MESSAGES) == set(en.MESSAGES)


def test_catalogs_use_the_same_placeholders_for_every_key():
    mismatched = {key for key in ru.MESSAGES if placeholders(ru.MESSAGES[key]) != placeholders(en.MESSAGES[key])}
    assert not mismatched, mismatched


def test_every_catalog_message_formats_with_its_own_placeholders():
    for catalog in (ru.MESSAGES, en.MESSAGES):
        for template in catalog.values():
            template.format(**dict.fromkeys(placeholders(template), "x"))      # no stray braces, no IndexError


def test_english_catalog_has_no_cyrillic_and_russian_one_is_really_russian():
    cyrillic = re.compile("[А-Яа-яЁё]")
    leaked = [key for key, text in en.MESSAGES.items() if cyrillic.search(text)]
    assert not leaked, leaked
    untranslated = [key for key, text in ru.MESSAGES.items() if not cyrillic.search(text) and text != en.MESSAGES[key]]
    assert not untranslated, untranslated


def test_default_language_comes_from_config():
    assert i18n.get_language() == config.LANGUAGE


def test_t_follows_the_language_setting():
    runtime.set_value("language", "en")
    assert i18n.t("lang_set", language="en") == en.MESSAGES["lang_set"].format(language="en")
    runtime.set_value("language", "ru")
    assert i18n.t("lang_set", language="ru") == ru.MESSAGES["lang_set"].format(language="ru")
    assert en.MESSAGES["lang_set"] != ru.MESSAGES["lang_set"]


def test_explicit_language_argument_wins():
    runtime.set_value("language", "ru")
    assert i18n.t("lang_set", language="en", lang="en") == en.MESSAGES["lang_set"].format(language="en")


def test_unknown_key_returns_the_key_instead_of_crashing_a_handler(caplog):
    assert i18n.t("no_such_key") == "no_such_key"
    assert "no_such_key" in caplog.text


def test_language_setting_is_validated():
    assert runtime.parse("language", " RU ") == "ru"
    with pytest.raises(ValueError):
        runtime.parse("language", "de")


def test_language_survives_load_from_database_and_ignores_garbage():
    runtime.load({"language": "ru"})
    assert i18n.get_language() == "ru"
    runtime.load({"language": "klingon"})
    assert i18n.get_language() == "ru"


def test_reset_returns_to_the_configured_language():
    runtime.set_value("language", "ru" if config.LANGUAGE == "en" else "en")
    runtime.reset("language")
    assert i18n.get_language() == config.LANGUAGE
