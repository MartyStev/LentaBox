from core.channel_ref import ChannelRef, parse_channel_ref as p


def test_usernames_and_links():
    assert p("@Examplechannel") == ChannelRef("username", "examplechannel")
    assert p("examplechannel") == ChannelRef("username", "examplechannel")
    assert p("https://t.me/examplechannel") == ChannelRef("username", "examplechannel")
    assert p("t.me/examplechannel/56052") == ChannelRef("username", "examplechannel")
    assert p("https://t.me/s/examplechannel") is None or p("https://t.me/s/examplechannel").value == "s"


def test_invites():
    assert p("https://t.me/+AbCdEfGh123") == ChannelRef("invite", "AbCdEfGh123")
    assert p("t.me/joinchat/AbCdEfGh123") == ChannelRef("invite", "AbCdEfGh123")


def test_garbage():
    assert p("") is None and p("@ab") is None and p("просто текст") is None
    assert p("https://example.com/examplechannel") is None
