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

    def test_deduplicate_results_keeps_first_url(self):
        results = [
            search_tool.normalize_result(
                source="tavily",
                title="First",
                url="https://example.com/a",
                content="one",
                language="zh",
            ),
            search_tool.normalize_result(
                source="google",
                title="Duplicate",
                url="https://example.com/a",
                content="two",
                language="en",
            ),
            search_tool.normalize_result(
                source="newsapi",
                title="Second",
                url="https://example.com/b",
                content="three",
                language="en",
            ),
        ]

        deduplicated = search_tool.deduplicate_results(results)

        self.assertEqual(len(deduplicated), 2)
        self.assertEqual(deduplicated[0]["title"], "First")
        self.assertEqual(deduplicated[1]["title"], "Second")

    def test_merge_results_deduplicates_and_adds_source_ids(self):
        results = [
            search_tool.normalize_result(
                source="tavily",
                title="First",
                url="https://example.com/a",
                content="one",
                language="zh",
            ),
            search_tool.normalize_result(
                source="google",
                title="Duplicate",
                url="https://example.com/a",
                content="two",
                language="en",
            ),
        ]

        merged = search_tool.merge_results(results)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source_id"], 1)
        self.assertEqual(merged[0]["domain"], "example.com")

    @patch.dict(
        "os.environ",
        {
            "TAVILY_API_KEY": "test-tavily",
            "SERPER_API_KEY": "test-serper",
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
            "SERPER_API_KEY": "test-serper",
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

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-serper"}, clear=True)
    @patch("search_tool.requests.post")
    def test_google_uses_serper_organic_results(self, requests_post):
        response = requests_post.return_value
        response.json.return_value = {
            "organic": [
                {
                    "title": "标题",
                    "link": "https://example.com/result",
                    "snippet": "摘要",
                }
            ]
        }

        results = search_tool.search_google("查询", language="zh")

        requests_post.assert_called_once()
        self.assertEqual(
            requests_post.call_args.args[0],
            "https://google.serper.dev/search",
        )
        self.assertEqual(
            requests_post.call_args.kwargs["headers"]["X-API-KEY"],
            "test-serper",
        )
        self.assertEqual(
            requests_post.call_args.kwargs["headers"]["Content-Type"],
            "application/json",
        )
        self.assertEqual(requests_post.call_args.kwargs["json"]["q"], "查询")
        self.assertEqual(requests_post.call_args.kwargs["json"]["num"], 5)
        self.assertEqual(requests_post.call_args.kwargs["json"]["hl"], "zh-cn")
        self.assertEqual(results[0]["source"], "google")
        self.assertEqual(results[0]["language"], "zh")
        self.assertEqual(results[0]["title"], "标题")
        self.assertEqual(results[0]["url"], "https://example.com/result")
        self.assertEqual(results[0]["content"], "摘要")

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-serper"}, clear=True)
    @patch("search_tool.requests.post")
    def test_google_uses_serper_english_parameters(self, requests_post):
        response = requests_post.return_value
        response.json.return_value = {"organic": []}

        search_tool.search_google("latest AI news", language="en", max_results=3)

        payload = requests_post.call_args.kwargs["json"]
        self.assertEqual(payload["q"], "latest AI news")
        self.assertEqual(payload["num"], 3)
        self.assertEqual(payload["hl"], "en")
        self.assertEqual(payload["gl"], "us")

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
