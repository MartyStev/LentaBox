"""Telegram entities to Bot API HTML: correct nesting for any combination."""
import html
import re
from types import SimpleNamespace

from core.entities import to_html


class MessageEntityBold(SimpleNamespace):
    pass


class MessageEntityItalic(SimpleNamespace):
    pass


class MessageEntityUnderline(SimpleNamespace):
    pass


class MessageEntityTextUrl(SimpleNamespace):
    pass


class MessageEntityCode(SimpleNamespace):
    pass


TAG_RE = re.compile(r"<(/?)([a-z-]+)[^>]*>")


def assert_well_formed(markup: str) -> None:
    """Each closing tag closes the most recently opened one, as the Bot API parser requires."""
    stack = []
    for closing, name in TAG_RE.findall(markup):
        if closing:
            assert stack and stack[-1] == name, f"bad nesting in {markup!r}"
            stack.pop()
        else:
            stack.append(name)
    assert not stack, f"unclosed tags in {markup!r}"


def plain(markup: str) -> str:
    return html.unescape(TAG_RE.sub("", markup))


def test_equal_ranges_close_in_reverse_order():
    out = to_html("Hello world", [MessageEntityBold(offset=0, length=5), MessageEntityItalic(offset=0, length=5)])
    assert out == "<b><i>Hello</i></b> world"
    assert_well_formed(out)


def test_bold_link_headline_is_valid():
    out = to_html("Hello world", [MessageEntityBold(offset=0, length=5),
                                  MessageEntityTextUrl(offset=0, length=5, url="https://x.y")])
    assert_well_formed(out) and plain(out) == "Hello world"
    assert "<a href" in out and "</a>" in out


def test_partially_overlapping_entities_are_split_not_crossed():
    out = to_html("0123456789", [MessageEntityBold(offset=0, length=5), MessageEntityItalic(offset=3, length=5)])
    assert_well_formed(out)
    assert plain(out) == "0123456789"
    assert "<b>012<i>34</i></b><i>567</i>89" == out


def test_three_way_overlap_and_nesting_stay_well_formed():
    text = "abcdefghijklmnop"
    ents = [MessageEntityBold(offset=0, length=8), MessageEntityItalic(offset=4, length=8),
            MessageEntityUnderline(offset=6, length=4), MessageEntityCode(offset=2, length=2)]
    out = to_html(text, ents)
    assert_well_formed(out) and plain(out) == text
    assert "<code>cd</code>" in out


def test_tg_links_only_resolve_is_allowed():
    link = lambda url: to_html("abc", [MessageEntityTextUrl(offset=0, length=3, url=url)])  # noqa: E731
    assert link("tg://resolve?domain=durov") is not None
    assert link("tg://proxy?server=x") is None and link("tg://user?id=1") is None


def test_entities_are_clamped_and_escaped():
    out = to_html("a<b", [MessageEntityBold(offset=0, length=50)])
    assert out == "<b>a&lt;b</b>"
    assert to_html("abc", [MessageEntityBold(offset=5, length=2)]) is None


def test_offset_inside_surrogate_pair_returns_none_not_a_broken_string():
    """An offset inside a surrogate pair used to yield a lone surrogate and break history writes."""
    emoji = "a😀b"                                     # "😀" takes two UTF-16 code units: offsets 1 and 2
    assert to_html(emoji, [MessageEntityBold(offset=2, length=1)]) is None
    out = to_html(emoji, [MessageEntityBold(offset=1, length=2)])
    assert out == "a<b>😀</b>b"
    out.encode("utf-8")
