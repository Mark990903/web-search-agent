import unittest
from unittest.mock import patch

import agent


class AgentSearchTests(unittest.TestCase):
    def test_build_source_stats_counts_engine_and_language(self):
        results = [
            {"source": "tavily", "language": "zh"},
            {"source": "google", "language": "en"},
            {"source": "google", "language": "en"},
        ]

        stats = agent.build_source_stats(results)

        self.assertEqual(stats["total_sources"], 3)
        self.assertEqual(stats["by_engine"], {"tavily": 1, "google": 2})
        self.assertEqual(stats["by_language"], {"zh": 1, "en": 2})

    def test_build_context_truncates_source_content(self):
        context = agent.build_context(
            [
                {
                    "source_id": 1,
                    "source": "tavily",
                    "language": "zh",
                    "title": "标题",
                    "url": "https://example.com",
                    "domain": "example.com",
                    "published_at": "",
                    "content": "a" * 900,
                }
            ]
        )

        self.assertIn("a" * agent.SOURCE_CONTENT_MAX_CHARS, context)
        self.assertNotIn("a" * (agent.SOURCE_CONTENT_MAX_CHARS + 1), context)

    def test_llm_timeout_is_180_seconds(self):
        self.assertEqual(agent.LLM_TIMEOUT_SECONDS, 180.0)

    @patch("agent.multi_source_search")
    def test_run_bilingual_search_keeps_chinese_then_english_order(
        self,
        multi_source_search,
    ):
        cn_payload = {"results": [{"title": "中文"}]}
        en_payload = {"results": [{"title": "English"}]}

        def fake_search(*args, **kwargs):
            if kwargs["language"] == "zh":
                return cn_payload
            return en_payload

        multi_source_search.side_effect = fake_search

        cn_search, en_search = agent.run_bilingual_search(
            query="中文问题",
            english_query="english query",
            time_range=None,
        )

        self.assertEqual(cn_search, cn_payload)
        self.assertEqual(en_search, en_payload)

    @patch("agent.generate_report")
    @patch("agent.run_bilingual_search")
    @patch("agent.translate_query_to_english")
    def test_summarize_search_uses_bilingual_sources_without_real_apis(
        self,
        translate_query_to_english,
        run_bilingual_search,
        generate_report,
    ):
        translate_query_to_english.return_value = "latest AI news"
        run_bilingual_search.return_value = (
            {
                "results": [
                    {
                        "source": "tavily",
                        "language": "zh",
                        "title": "中文新闻",
                        "url": "https://example.com/zh",
                        "content": "中文摘要",
                    }
                ],
                "enabled_sources": ["tavily"],
                "skipped_sources": [],
                "failed_sources": [],
            },
            {
                "results": [
                    {
                        "source": "google",
                        "language": "en",
                        "title": "AI News",
                        "url": "https://example.com/en",
                        "content": "English summary",
                    }
                ],
                "enabled_sources": ["google"],
                "skipped_sources": [],
                "failed_sources": [],
            },
        )
        generate_report.return_value = "中文报告"

        report = agent.summarize_search("今天 AI 新闻")

        self.assertEqual(report["english_query"], "latest AI news")
        self.assertIn("# Research Report", report["chinese"])
        self.assertIn("中文报告", report["chinese"])
        self.assertIn("research_id", report)
        self.assertIn("Research Metadata", report["chinese"])
        self.assertEqual(report["english"], agent.ENGLISH_REPORT_PLACEHOLDER)
        self.assertFalse(report["english_report_available"])
        self.assertEqual(report["source_stats"]["total_sources"], 2)
        self.assertEqual(report["source_stats"]["by_language"], {"zh": 1, "en": 1})
        self.assertEqual(report["enabled_sources"], ["google", "tavily"])
        self.assertEqual(report["sources"][0]["source_id"], 1)
        self.assertEqual(report["sources"][1]["source_id"], 2)
        generate_report.assert_called_once()


if __name__ == "__main__":
    unittest.main()
