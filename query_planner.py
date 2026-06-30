import json
import logging
import os
import re
from datetime import date
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

logger = logging.getLogger(__name__)
PLANNER_TIMEOUT_SECONDS = 60.0
MAX_SUB_QUERIES = 5
MIN_RESEARCH_SUB_QUERIES = 3
CURRENT_INTENT_PATTERN = re.compile(
    r"(现状|当前|目前|最新|今天|current|latest|today|now|as of)",
    re.IGNORECASE,
)
EXPLICIT_HISTORY_PATTERN = re.compile(
    r"(\b20\d{2}\b|过去几年|近几年|历年|历史|past few years|last few years|"
    r"historical|since\s+20\d{2}|from\s+20\d{2})",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def build_fallback_plan(user_query: str, error: str | None = None) -> dict[str, Any]:
    """Build a plain-search plan used when planner output is unavailable."""
    plan: dict[str, Any] = {
        "is_research_task": False,
        "main_topic": user_query,
        "sub_queries": [
            {
                "title": "主查询",
                "query_zh": user_query,
                "query_en": user_query,
                "purpose": "执行普通搜索",
            }
        ],
        "json_parse_success": False,
    }

    if error:
        plan["planner_error"] = error

    return plan


def create_planner_client() -> OpenAI:
    """Create an OFOX OpenAI-compatible client for query planning."""
    api_key = os.getenv("OFOX_API_KEY")
    base_url = os.getenv("OFOX_BASE_URL")

    if not api_key:
        raise ValueError("未配置 OFOX_API_KEY")

    if not base_url:
        raise ValueError("未配置 OFOX_BASE_URL")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=PLANNER_TIMEOUT_SECONDS,
        max_retries=0,
    )


def extract_json_object(content: str) -> dict[str, Any]:
    """Parse a JSON object from model output, including fenced JSON blocks."""
    text = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def normalize_sub_query(item: Any, fallback_query: str, index: int) -> dict[str, str]:
    """Normalize one planner sub-query item into the public schema."""
    if not isinstance(item, dict):
        item = {}

    title = str(item.get("title") or f"子问题 {index}").strip()
    query_zh = str(item.get("query_zh") or fallback_query).strip()
    query_en = str(item.get("query_en") or query_zh).strip()
    purpose = str(item.get("purpose") or "补充搜索证据").strip()

    return {
        "title": title,
        "query_zh": query_zh,
        "query_en": query_en,
        "purpose": purpose,
    }


def has_current_intent(user_query: str) -> bool:
    """Return whether the user asks for current/latest information."""
    return bool(CURRENT_INTENT_PATTERN.search(user_query))


def has_explicit_history_request(user_query: str) -> bool:
    """Return whether the user explicitly asks for historical years/ranges."""
    return bool(EXPLICIT_HISTORY_PATTERN.search(user_query))


def remove_unrequested_past_years(query: str, current_year: int) -> str:
    """Remove model-added years before the current year from a query string."""

    def replace(match: re.Match[str]) -> str:
        year = int(match.group(1))
        if year < current_year:
            return ""
        return match.group(0)

    cleaned = YEAR_PATTERN.sub(replace, query)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def ensure_current_query_language(query: str, current_year: int) -> str:
    """Ensure an English query carries current/latest timing language."""
    lower_query = query.lower()
    current_markers = [
        "current",
        "latest",
        str(current_year),
        f"as of {current_year}",
    ]

    if any(marker in lower_query for marker in current_markers):
        return query

    return f"{query} current {current_year}".strip()


def normalize_time_sensitive_queries(
    sub_queries: list[dict[str, str]],
    user_query: str,
    current_year: int,
) -> list[dict[str, str]]:
    """Guard planner output against unrequested stale year keywords."""
    if not has_current_intent(user_query) or has_explicit_history_request(user_query):
        return sub_queries

    normalized_sub_queries = []
    for item in sub_queries:
        normalized_item = dict(item)
        normalized_item["query_zh"] = remove_unrequested_past_years(
            normalized_item.get("query_zh", ""),
            current_year,
        )
        query_en = remove_unrequested_past_years(
            normalized_item.get("query_en", ""),
            current_year,
        )
        normalized_item["query_en"] = ensure_current_query_language(
            query_en,
            current_year,
        )
        normalized_sub_queries.append(normalized_item)

    return normalized_sub_queries


def validate_plan(
    raw_plan: dict[str, Any],
    user_query: str,
    current_year: int | None = None,
) -> dict[str, Any]:
    """Validate and coerce model output into a safe planner payload."""
    current_year = current_year or date.today().year
    is_research_task = bool(raw_plan.get("is_research_task"))
    main_topic = str(raw_plan.get("main_topic") or user_query).strip()
    raw_sub_queries = raw_plan.get("sub_queries")

    if not isinstance(raw_sub_queries, list):
        raw_sub_queries = []

    sub_queries = [
        normalize_sub_query(item, user_query, index)
        for index, item in enumerate(raw_sub_queries[:MAX_SUB_QUERIES], start=1)
    ]

    if is_research_task and not (
        MIN_RESEARCH_SUB_QUERIES <= len(sub_queries) <= MAX_SUB_QUERIES
    ):
        raise ValueError("研究任务必须包含 3-5 个 sub_queries")

    if not is_research_task:
        sub_queries = sub_queries[:1] or build_fallback_plan(user_query)["sub_queries"]

    sub_queries = normalize_time_sensitive_queries(
        sub_queries=sub_queries,
        user_query=user_query,
        current_year=current_year,
    )

    return {
        "is_research_task": is_research_task,
        "main_topic": main_topic,
        "sub_queries": sub_queries,
        "json_parse_success": True,
    }


def build_planner_prompt(user_query: str) -> str:
    """Build the strict JSON planning prompt."""
    current_date = date.today()
    current_year = current_date.year
    return f"""
你是 Web Search Agent V3 的 Query Planner。你的任务是判断用户问题是普通搜索还是研究型问题，并输出可直接用于搜索的 JSON。

当前系统日期：
{current_date.isoformat()}

用户原始问题：
{user_query}

判断标准：
- 普通搜索：用户只想知道一个事实、最新消息、新闻列表、定义或单一答案。
- 研究型问题：用户要求分析、研究、对比、包含多个维度，或需要系统性收集证据。

普通搜索例子：
- 今天 AI 有哪些新闻？
- OpenAI 最新模型是什么？

研究型问题例子：
- 帮我研究 AI Agent 市场现状，包括主要公司、融资、商业模式和趋势。
- 分析 AI 产品经理岗位发展前景。
- 对比 LangGraph、CrewAI、AutoGen 的优缺点。

输出要求：
1. 只输出一个 JSON object，不要 Markdown，不要解释。
2. JSON 字段必须为：
{{
  "is_research_task": true 或 false,
  "main_topic": "主题",
  "sub_queries": [
    {{
      "title": "子问题标题",
      "query_zh": "中文搜索查询",
      "query_en": "English search query",
      "purpose": "搜索目的"
    }}
  ]
}}
3. 如果是普通搜索，sub_queries 只保留 1 个主查询。
4. 如果是研究型问题，sub_queries 必须拆解为 3-5 个互补子问题。
5. query_zh 和 query_en 要适合直接搜索，必要时补充行业、对象等关键词。
6. 当前年份是 {current_year}。如果用户说“现状 / 当前 / 最新 / today / current”等当前时间语义，query_en 应使用 current、latest、{current_year} 或 as of {current_year}。
7. 不要擅自添加用户没有要求的过去年份，例如 2023、2024、2025。
8. 只有当用户明确要求“2024”“2025”“过去几年”“past few years”等历史年份或历史范围时，才允许生成对应年份。
9. 如果用户没有明确要求历史年份，默认使用当前日期和当前年份来规划搜索词。
"""


def plan_queries(user_query: str) -> dict[str, Any]:
    """Plan search queries for a user question.

    Args:
        user_query: Original user query.

    Returns:
        Planner payload. Failures fall back to plain-search mode.
    """
    logger.info("Query Planner enabled for query planning")

    try:
        model = os.getenv("OFOX_MODEL")
        if not model:
            raise ValueError("未配置 OFOX_MODEL")

        client = create_planner_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You output strict JSON only.",
                },
                {
                    "role": "user",
                    "content": build_planner_prompt(user_query),
                },
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content or ""
        raw_plan = extract_json_object(content)
        plan = validate_plan(raw_plan, user_query, current_year=date.today().year)

        logger.info(
            "Query Planner completed is_research_task=%s sub_query_count=%s "
            "json_parse_success=%s",
            plan["is_research_task"],
            len(plan["sub_queries"]),
            plan["json_parse_success"],
        )
        return plan
    except Exception as error:
        logger.warning("Query Planner failed: %s", error)
        return build_fallback_plan(user_query, error=str(error))
