import unittest

from peacock.vyakarana import (
    EXPECTED_SUTRAS, EXECUTABLE_RULE_IDS, CorpusError, PratyaharaError,
    SandhiError, all_sutras, chapter, expand, get_sutra, join, literature, search,
)


class CorpusTests(unittest.TestCase):
    def test_complete_text_corpus_and_endpoints(self):
        self.assertEqual(len(all_sutras()), EXPECTED_SUTRAS)
        self.assertEqual(EXPECTED_SUTRAS, 3983)
        self.assertEqual(get_sutra("1.1.1").text, "वृद्धिरादैच्")
        self.assertEqual(get_sutra("8.4.68").text, "अ अ")
        self.assertEqual(len({sutra.id for sutra in all_sutras()}), EXPECTED_SUTRAS)

    def test_anuvritti_and_adhikara_references(self):
        inherited = get_sutra("1.1.3").anuvritti
        self.assertEqual([ref.display() for ref in inherited], ["वृद्धिः [1.1.1]", "गुणः [1.1.2]"])
        adhikara = get_sutra("8.4.68").adhikara
        self.assertEqual([ref.sutra_id for ref in adhikara], ["8.2.1", "8.2.108"])

    def test_search_and_chapter(self):
        self.assertEqual(search("वृद्धिरादैच्", 1)[0].id, "1.1.1")
        self.assertTrue(search("संज्ञा", 5))
        self.assertTrue(all(sutra.id.startswith("1.1.") for sutra in chapter(1, 1)))

    def test_invalid_corpus_queries(self):
        with self.assertRaises(CorpusError):
            get_sutra("9.9.9")
        with self.assertRaises(CorpusError):
            search("", 10)
        with self.assertRaises(CorpusError):
            search("गुण", 0)

    def test_literature_scope_is_explicit(self):
        rows = literature()
        self.assertGreaterEqual(len(rows), 17)
        self.assertTrue(any("complete sūtra text corpus" in row for row in rows))
        self.assertTrue(any("काशिका" in row and "catalogue only" in row for row in rows))

    def test_executable_ids_exist_in_corpus(self):
        for rule_id in EXECUTABLE_RULE_IDS:
            self.assertEqual(get_sutra(rule_id).id, rule_id)


class PratyaharaTests(unittest.TestCase):
    def test_vowels_and_consonants(self):
        self.assertEqual(expand("अच्"), tuple("अइउऋऌएओऐऔ"))
        consonants = expand("हल्")
        self.assertEqual(len(consonants), 33)
        self.assertEqual(len(set(consonants)), 33)
        self.assertEqual(len(expand("अल्")), 42)

    def test_standard_pratyaharas(self):
        self.assertEqual(expand("इक्"), ("इ", "उ", "ऋ", "ऌ"))
        self.assertEqual(expand("यण्"), ("य", "व", "र", "ल"))
        self.assertEqual(expand("एङ्"), ("ए", "ओ"))
        self.assertEqual(expand("ऐच्"), ("ऐ", "औ"))

    def test_invalid_pratyahara(self):
        for value in ("", "अ", "कच्", "चअ"):
            with self.subTest(value=value), self.assertRaises(PratyaharaError):
                expand(value)


class SandhiTests(unittest.TestCase):
    def test_savarna_dirgha(self):
        cases = [("राम", "आलयः", "रामालयः"), ("गुरु", "उपदेशः", "गुरूपदेशः"), ("नदी", "ईश्वरः", "नदीश्वरः")]
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                result = join(left, right)
                self.assertEqual(result.text, expected)
                self.assertEqual(result.rule_id, "6.1.101")

    def test_guna_and_vrddhi(self):
        cases = [("राम", "इन्द्रः", "रामेन्द्रः", "6.1.87"), ("महा", "ऋषिः", "महर्षिः", "6.1.87"), ("देव", "औदार्यम्", "देवौदार्यम्", "6.1.88")]
        for left, right, expected, rule in cases:
            with self.subTest(left=left, right=right):
                result = join(left, right)
                self.assertEqual(result.text, expected)
                self.assertEqual(result.rule_id, rule)

    def test_yana(self):
        cases = [("नदी", "अत्र", "नद्यत्र"), ("सु", "आगतम्", "स्वागतम्"), ("इति", "आदि", "इत्यादि")]
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                result = join(left, right)
                self.assertEqual(result.text, expected)
                self.assertEqual(result.rule_id, "6.1.77")

    def test_sandhi_rejects_unknown_or_ambiguous_boundaries(self):
        with self.assertRaises(SandhiError):
            join("ए", "अत्र")
        with self.assertRaises(SandhiError):
            join("राम्", "अत्र")
        with self.assertRaises(SandhiError):
            join("राम", "चित्रम्")


if __name__ == "__main__":
    unittest.main()
