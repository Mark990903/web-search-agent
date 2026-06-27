from datetime import date
import unittest
from unittest.mock import Mock, patch

import search_tool
from time_awareness import TimeRange


class SearchTimeFilterTests(unittest.TestCase):
    def setUp(self):
        self.time_range = TimeRange(
            label="最近7天",
            start_date=date(2026, 6, 20),
            end_date=date(2026, 6, 26),
        )

    @patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"})
    @patch("search_tool.TavilyClient")
    def test_tavily_receives_date_range(self, tavily_client):
        client = Mock()
        client.search.return_value = {"results": []}
        tavily_client.return_value = client

        search_tool.search_tavily("query", time_range=self.time_range)

        client.search.assert_called_once()
        params = client.search.call_args.kwargs
        self.assertEqual(params["start_date"], "2026-06-20")
        self.assertEqual(params["end_date"], "2026-06-26")

    @patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"})
    @patch("search_tool.TavilyClient")
    def test_tavily_receives_single_day_range(self, tavily_client):
        today_range = TimeRange(
            label="今天",
            start_date=date(2026, 6, 26),
            end_date=date(2026, 6, 26),
        )
        client = Mock()
        client.search.return_value = {"results": []}
        tavily_client.return_value = client

        search_tool.search_tavily("query", time_range=today_range)

        params = client.search.call_args.kwargs
        self.assertEqual(params["time_range"], "day")
        self.assertNotIn("start_date", params)
        self.assertNotIn("end_date", params)

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("search_tool.requests.post")
    def test_google_receives_date_range(self, requests_post):
        response = Mock()
        response.json.return_value = {"organic": []}
        requests_post.return_value = response

        search_tool.search_google("query", time_range=self.time_range)

        payload = requests_post.call_args.kwargs["json"]
        self.assertEqual(
            payload["q"],
            "query after:2026-06-20 before:2026-06-26",
        )

    @patch.dict("os.environ", {"NEWS_API_KEY": "test-key"})
    @patch("search_tool.requests.get")
    def test_newsapi_receives_date_range(self, requests_get):
        response = Mock()
        response.json.return_value = {"articles": []}
        requests_get.return_value = response

        search_tool.search_newsapi("query", time_range=self.time_range)

        params = requests_get.call_args.kwargs["params"]
        self.assertEqual(params["from"], "2026-06-20")
        self.assertEqual(params["to"], "2026-06-26")

    def test_published_at_fallback_filter(self):
        self.assertTrue(
            search_tool.is_within_time_range("2026-06-21T08:00:00Z", self.time_range)
        )
        self.assertFalse(
            search_tool.is_within_time_range("2026-06-19T08:00:00Z", self.time_range)
        )


if __name__ == "__main__":
    unittest.main()
