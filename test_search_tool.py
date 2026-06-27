from datetime import date
import unittest
from unittest.mock import patch

import search_tool
from time_awareness import TimeRange, detect_time_range


class SearchToolTests(unittest.TestCase):
    def setUp(self):
        self.time_range = TimeRange(
            label="今天",
            start_date=date(2026, 6, 27),
            end_date=date(2026, 6, 27),
        )

    def test_normalize_result_returns_language_field(self):
        result = search_tool.normalize_result(
            source="google",
            title="Title",
            url="https://example.com/article",
            content="Summary",
            language="zh",
        )

        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["source_id"], "")
        self.assertEqual(result["domain"], "example.com")

    @patch.dict(
        "os.environ",
        {
            "TAVILY_API_KEY": "test-tavily",
            "GOOGLE_API_KEY": "test-google",
            "GOOGLE_CSE_ID": "test-cse",
            "NEWS_API_KEY": "test-news",
        },
        clear=True,
    )
    def test_multi_source_search_accepts_language_parameter(self):
        with patch("search_tool.search_tavily", return_value=[]), \
             patch("search_tool.search_google", return_value=[]) as google_search, \
             patch("search_tool.search_newsapi", return_value=[]):
            search_tool.multi_source_search("query", language="zh")

        self.assertEqual(google_search.call_args.kwargs["language"], "zh")

    @patch.dict(
        "os.environ",
        {
            "TAVILY_API_KEY": "test-tavily",
            "GOOGLE_API_KEY": "test-google",
            "GOOGLE_CSE_ID": "test-cse",
            "NEWS_API_KEY": "test-news",
        },
        clear=True,
    )
    def test_multi_source_search_accepts_time_range_parameter(self):
        with patch("search_tool.search_tavily", return_value=[]) as tavily_search, \
             patch("search_tool.search_google", return_value=[]), \
             patch("search_tool.search_newsapi", return_value=[]):
            search_tool.multi_source_search("query", time_range=self.time_range)

        self.assertEqual(tavily_search.call_args.kwargs["time_range"], self.time_range)

    def test_detect_today_query_returns_today(self):
        time_range = detect_time_range(
            "今天 AI 领域发生了哪些重要新闻？",
            today=date(2026, 6, 27),
        )

        self.assertEqual(time_range.label, "今天")
        self.assertEqual(time_range.start_date, date(2026, 6, 27))
        self.assertEqual(time_range.end_date, date(2026, 6, 27))

    @patch.dict("os.environ", {}, clear=True)
    def test_unconfigured_sources_do_not_raise(self):
        google_results = search_tool.search_google("query")
        newsapi_results = search_tool.search_newsapi("query")
        tavily_results = search_tool.search_tavily("query")
        multi_source_response = search_tool.multi_source_search(
            "query",
            include_metadata=True,
        )

        self.assertEqual(google_results, [])
        self.assertEqual(newsapi_results, [])
        self.assertEqual(tavily_results, [])
        self.assertEqual(multi_source_response["results"], [])
        self.assertEqual(len(multi_source_response["skipped_sources"]), 3)


if __name__ == "__main__":
    unittest.main()
