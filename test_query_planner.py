import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import agent
import query_planner


def make_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


def make_client(content: str) -> SimpleNamespace:
    create = Mock(return_value=make_response(content))
    completions = SimpleNamespace(create=create)
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat)


class QueryPlannerTests(unittest.TestCase):
    @patch.dict("os.environ", {"OFOX_MODEL": "test-model"})
    @patch("query_planner.create_planner_client")
    def test_simple_search_returns_plain_mode(self, create_planner_client):
        content = json.dumps(
            {
                "is_research_task": False,
                "main_topic": "OpenAI 最新模型",
                "sub_queries": [
                    {
                        "title": "主查询",
                        "query_zh": "OpenAI 最新模型",
                        "query_en": "OpenAI latest model",
                        "purpose": "了解最新模型信息",
                    }
                ],
            }
        )
        create_planner_client.return_value = make_client(content)

        plan = query_planner.plan_queries("OpenAI 最新模型是什么？")

        self.assertFalse(plan["is_research_task"])
        self.assertEqual(len(plan["sub_queries"]), 1)
        self.assertTrue(plan["json_parse_success"])

    @patch.dict("os.environ", {"OFOX_MODEL": "test-model"})
    @patch("query_planner.create_planner_client")
    def test_research_question_returns_three_to_five_sub_queries(
        self,
        create_planner_client,
    ):
        content = json.dumps(
            {
                "is_research_task": True,
                "main_topic": "AI Agent 市场现状",
                "sub_queries": [
                    {
                        "title": "市场现状",
                        "query_zh": "AI Agent 市场现状 2026",
                        "query_en": "AI Agent market landscape 2026",
                        "purpose": "了解整体市场发展情况",
                    },
                    {
                        "title": "主要公司",
                        "query_zh": "AI Agent 主要公司 2026",
                        "query_en": "leading AI Agent companies 2026",
                        "purpose": "识别主要参与者",
                    },
                    {
                        "title": "融资情况",
                        "query_zh": "AI Agent 融资 2026",
                        "query_en": "AI Agent funding 2026",
                        "purpose": "了解融资活跃度",
                    },
                ],
            }
        )
        create_planner_client.return_value = make_client(content)

        plan = query_planner.plan_queries(
            "帮我研究 AI Agent 市场现状，包括主要公司、融资、商业模式和趋势。"
        )

        self.assertTrue(plan["is_research_task"])
        self.assertGreaterEqual(len(plan["sub_queries"]), 3)
        self.assertLessEqual(len(plan["sub_queries"]), 5)
        self.assertTrue(plan["json_parse_success"])

    @patch.dict("os.environ", {"OFOX_MODEL": "test-model"})
    @patch("query_planner.create_planner_client")
    def test_json_parse_failure_falls_back_to_plain_search(
        self,
        create_planner_client,
    ):
        create_planner_client.return_value = make_client("not json")

        plan = query_planner.plan_queries("今天 AI 有哪些新闻？")

        self.assertFalse(plan["is_research_task"])
        self.assertEqual(len(plan["sub_queries"]), 1)
        self.assertFalse(plan["json_parse_success"])
        self.assertIn("planner_error", plan)

    @patch("agent.plan_queries")
    @patch("agent.generate_report")
    @patch("agent.run_bilingual_search")
    @patch("agent.translate_query_to_english")
    def test_use_planner_false_does_not_call_planner(
        self,
        translate_query_to_english,
        run_bilingual_search,
        generate_report,
        plan_queries,
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
                "results": [],
                "enabled_sources": [],
                "skipped_sources": [],
                "failed_sources": [],
            },
        )
        generate_report.return_value = "中文报告"

        report = agent.summarize_search("今天 AI 新闻", use_planner=False)

        plan_queries.assert_not_called()
        self.assertFalse(report["planner"]["enabled"])
        self.assertEqual(report["chinese"], "中文报告")

    @patch("agent.plan_queries", side_effect=RuntimeError("planner boom"))
    @patch("agent.generate_report")
    @patch("agent.run_bilingual_search")
    @patch("agent.translate_query_to_english")
    def test_planner_failure_still_returns_report_structure(
        self,
        translate_query_to_english,
        run_bilingual_search,
        generate_report,
        plan_queries,
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
                "results": [],
                "enabled_sources": [],
                "skipped_sources": [],
                "failed_sources": [],
            },
        )
        generate_report.return_value = "中文报告"

        report = agent.summarize_search("今天 AI 新闻")

        plan_queries.assert_called_once()
        self.assertEqual(report["chinese"], "中文报告")
        self.assertIn("planner_error", report)
        self.assertEqual(report["sources"][0]["source_id"], 1)
        self.assertTrue(
            any(
                item.get("source") == "query_planner"
                for item in report.get("failed_sources", [])
            )
        )


if __name__ == "__main__":
    unittest.main()
