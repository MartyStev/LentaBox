"""Formatting of the original: Telegram entities (MTProto) -> Bot API HTML.

Entity offsets are counted in UTF-16 units, as in Telegram. The Bot API parser requires strict
nesting: a closing tag must close the most recently opened one. Telegram, however, allows entities
with the same range in any order and partially overlapping ones, so tags are tracked with a
stack: at a boundary we close everything down to the deepest entity that ends there and reopen those
that are still active. Works with Telethon objects by class name, so tests do not need to import Telethon.
"""

import html

TAGS = {
    "MessageEntityBold": ("<b>", "</b>"),
    "MessageEntityItalic": ("<i>", "</i>"),
    "MessageEntityUnderline": ("<u>", "</u>"),
    "MessageEntityStrike": ("<s>", "</s>"),
    "MessageEntityCode": ("<code>", "</code>"),
    "MessageEntitySpoiler": ("<tg-spoiler>", "</tg-spoiler>"),
    "MessageEntityBlockquote": ("<blockquote>", "</blockquote>"),
}


def _tags(entity) -> tuple[str, str] | None:
    kind = type(entity).__name__
    if kind in TAGS:
        return TAGS[kind]
    if kind == "MessageEntityPre":
        language = getattr(entity, "language", "") or ""
        if language:
            return f'<pre><code class="language-{html.escape(language, quote=True)}">', "</code></pre>"
        return "<pre>", "</pre>"
    if kind == "MessageEntityTextUrl":
        url = getattr(entity, "url", "") or ""
        # For tg:// only resolve is allowed: otherwise any deep link could hide behind innocent-looking text
        if url.startswith(("http://", "https://", "tg://resolve?")):
            return f'<a href="{html.escape(url, quote=True)}">', "</a>"
    return None


def _spans(entities, total: int) -> list[tuple[int, int, str, str]]:
    """(start, end, opening, closing) of known entities within the text:
    longer ones before shorter ones at equal start, so that the outer tag opens first."""
    spans = []
    for order, entity in enumerate(entities):
        tags = _tags(entity)
        if tags is None:
            continue
        start, length = int(entity.offset), int(entity.length)
        end = min(start + length, total)
        if start < 0 or end <= start:
            continue
        spans.append((start, -length, order, end, tags))
    spans.sort()
    return [(start, end, open_tag, close_tag) for start, _, _, end, (open_tag, close_tag) in spans]


def to_html(text: str, entities) -> str | None:
    """HTML with the original's markup, or None if there is nothing to mark up (html.escape is enough then)."""
    if not text or not entities:
        return None
    units = text.encode("utf-16-le")
    total = len(units) // 2
    spans = _spans(entities, total)
    if not spans:
        return None
    boundaries = sorted({0, total} | {s[0] for s in spans} | {s[1] for s in spans})
    out: list[str] = []
    stack: list[tuple[int, int, str, str]] = []
    for index, position in enumerate(boundaries):
        if index:
            previous = boundaries[index - 1]
            out.append(html.escape(units[previous * 2: position * 2].decode("utf-16-le", "surrogatepass")))
        active = [s for s in spans if s[0] <= position < s[1]]
        # close everything, starting from the deepest entity that ends here
        ended = [i for i, s in enumerate(stack) if s not in active]
        reopen: list[tuple[int, int, str, str]] = []
        if ended:
            cut = ended[0]
            for span in reversed(stack[cut:]):
                out.append(span[3])
                if span in active:
                    reopen.append(span)
            del stack[cut:]
            reopen.reverse()
        for span in reopen + [s for s in active if s not in stack and s not in reopen]:
            out.append(span[2])
            stack.append(span)
    result = "".join(out)
    try:
        result.encode("utf-8")
    except UnicodeEncodeError:
        # offset fell inside a surrogate pair: the write would fail and the message would be treated as poison
        return None
    return result
