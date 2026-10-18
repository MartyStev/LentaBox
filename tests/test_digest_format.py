from core import digest


def row(text="Заголовок новости\nвторая строка", channel="@news", link="https://t.me/news/1"):
    return {"headline": digest.headline(text), "channel_label": channel, "link": link}


def test_headline_is_the_first_non_empty_line_cut_to_the_limit():
    assert digest.headline("\n\n  Первая строка  \nвторая") == "Первая строка"
    long = "слово " * 100
    result = digest.headline(long, limit=30)
    assert len(result) <= 30 and result.endswith("…")


def test_headline_of_empty_text_is_a_placeholder():
    assert digest.headline("   ") == "…"


def test_format_digest_lists_stories_with_channel_and_link():
    messages = digest.format_digest([row(), row(channel="@other", link="https://t.me/other/9")], lang="en")
    assert len(messages) == 1
    text = messages[0]
    assert "2" in text.splitlines()[0]
    assert "@news" in text and "@other" in text
    assert '<a href="https://t.me/news/1">' in text
    assert text.count("•") == 2


def test_digest_header_follows_the_language():
    ru = digest.format_digest([row()], lang="ru")[0]
    en = digest.format_digest([row()], lang="en")[0]
    assert ru.splitlines()[0] != en.splitlines()[0]


def test_headlines_and_channels_are_html_escaped():
    messages = digest.format_digest([row(text="a <b>&", channel="A < B")], lang="en")
    assert "a &lt;b&gt;&amp;" in messages[0]
    assert "A &lt; B" in messages[0]


def test_story_without_link_is_listed_without_a_link():
    messages = digest.format_digest([row(link=None)], lang="en")
    assert "<a href" not in messages[0] and "•" in messages[0]


def test_long_digest_is_split_into_several_messages_within_the_limit():
    rows = [row(text=f"Новость номер {i} " + "x" * 80, link=f"https://t.me/news/{i}") for i in range(200)]
    messages = digest.format_digest(rows, lang="en")
    assert len(messages) > 1
    assert all(len(m.encode("utf-16-le")) // 2 <= digest.MESSAGE_LIMIT for m in messages)
    assert sum(m.count("•") for m in messages) == 200               # nothing lost between parts
