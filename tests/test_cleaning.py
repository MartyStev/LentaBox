import unittest

from core import cleaning


class CleaningTests(unittest.TestCase):
    def test_strips_links_mentions_hashtags_and_emoji(self):
        text = "🔥 В Таиланде спасли капибар https://t.me/news/12 #новости @news_channel"
        self.assertEqual(cleaning.clean_text(text), "В Таиланде спасли капибар")

    def test_drops_promo_tail_lines(self):
        text = "Курс доллара вырос до 100 рублей\n\n📢 Подписаться на канал\nПрислать новость: @bot"
        self.assertEqual(cleaning.clean_text(text), "Курс доллара вырос до 100 рублей")

    def test_keeps_text_when_everything_looks_like_promo(self):
        self.assertEqual(cleaning.clean_text("Подписаться на канал"), "Подписаться на канал")

    def test_keeps_currency_and_percent_symbols(self):
        self.assertEqual(cleaning.clean_text("Рост на 5% до $100"), "Рост на 5% до $100")

    def test_matching_text_is_normalized_and_limited(self):
        self.assertEqual(cleaning.matching_text("  ЗАГОЛОВОК\n\nтекст  ", 9), "заголовок")

    def test_same_story_with_different_tails_matches_identically(self):
        a = cleaning.matching_text("Утки на рисовых полях\n\n📢 Подписаться на канал", 200)
        b = cleaning.matching_text("Утки на рисовых полях\n\nПрислать новость: @bot", 200)
        self.assertEqual(a, b)

    def test_headlines_about_joining_are_not_promo(self):
        self.assertEqual(
            cleaning.clean_text("Швеция присоединяется к НАТО"), "Швеция присоединяется к НАТО",
        )
        self.assertEqual(cleaning.clean_text("Температура -5°C"), "Температура -5°C")

    def test_ad_markers(self):
        self.assertTrue(cleaning.is_ad("Скидки! Реклама. erid: 2VtzqwP"))
        self.assertTrue(cleaning.is_ad("Покупайте #реклама"))
        self.assertTrue(cleaning.is_ad("На правах рекламы: новый банк"))
        self.assertTrue(cleaning.is_ad("Промокод NEWS даёт скидку"))
        self.assertFalse(cleaning.is_ad("Реклама сигарет в России запрещена"))


class EnglishCleaningTests(unittest.TestCase):
    def test_english_promo_tail_is_dropped(self):
        text = "Fed holds rates steady at 5.25%\n\nSubscribe to our channel\nFollow us on X"
        self.assertEqual(cleaning.clean_text(text), "Fed holds rates steady at 5.25%")

    def test_english_headlines_with_keywords_survive(self):
        self.assertEqual(cleaning.clean_text("Netflix subscribers fall for the first time"),
                         "Netflix subscribers fall for the first time")
        self.assertEqual(cleaning.clean_text("Sweden joins NATO after two years"), "Sweden joins NATO after two years")

    def test_english_ad_markers(self):
        self.assertTrue(cleaning.is_ad("Best VPN deal #ad"))
        self.assertTrue(cleaning.is_ad("This post is sponsored by Acme"))
        self.assertTrue(cleaning.is_ad("Use promo code NEWS10"))
        self.assertFalse(cleaning.is_ad("Government sponsored research shows"))


if __name__ == "__main__":
    unittest.main()
