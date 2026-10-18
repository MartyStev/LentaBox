import unittest

from core import similarity


class ClusterMatchTests(unittest.TestCase):
    def test_picks_most_similar_cluster(self):
        clusters = [(1, [1.0, 0.0], 1), (2, [0.7, 0.7], 1), (3, [0.0, 1.0], 1)]
        cluster_id, score = similarity.best_cluster_match([0.6, 0.8], clusters)
        self.assertEqual(cluster_id, 2)
        self.assertGreater(score, 0.97)

    def test_empty_or_mismatched_clusters_give_no_match(self):
        self.assertEqual(similarity.best_cluster_match([1.0, 0.0], []), (None, 0.0))
        self.assertEqual(
            similarity.best_cluster_match([1.0, 0.0], [(1, None, 1), (2, [1.0], 1)]),
            (None, 0.0),
        )

    def test_zero_vector_is_not_a_match(self):
        self.assertEqual(
            similarity.best_cluster_match([1.0, 0.0], [(1, [0.0, 0.0], 1)]), (None, 0.0),
        )

    def test_centroid_is_weighted_mean(self):
        merged = similarity.merge_centroid([1.0, 0.0], 3, [0.0, 4.0], max_weight=20)
        self.assertEqual(merged, [0.75, 1.0])

    def test_centroid_weight_is_capped(self):
        merged = similarity.merge_centroid([1.0, 0.0], 100, [0.0, 1.0], max_weight=1)
        self.assertEqual(merged, [0.5, 0.5])


class FuzzyTests(unittest.TestCase):
    def test_best_fuzzy_score(self):
        score = similarity.best_fuzzy_score("курс доллара вырос", ["погода в москве", "курс доллара вырос"])
        self.assertEqual(score, 100)
        self.assertEqual(similarity.best_fuzzy_score("текст", []), 0.0)

    def test_short_text_is_not_swallowed_by_long_candidate_with_same_words(self):
        """token_set_ratio used to return 100 when the words of a short post were all contained in a long one."""
        short = "курс доллара вырос"
        long = ("сегодня на торгах курс доллара вырос на фоне новостей о ставке, рубль ослаб, "
                "аналитики ждут дальнейшего движения и обсуждают прогнозы на неделю и месяц вперёд")
        self.assertLess(similarity.best_fuzzy_score(short, [long]), 88)
        same_length = "курс доллара вырос сильно"
        self.assertGreater(similarity.best_fuzzy_score(short, [same_length]), 88)


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
