import os
import requests
from dotenv import load_dotenv
from tavily import TavilyClient
from urllib.parse import urlparse
from datetime import datetime

load_dotenv()

_LOGGED_MESSAGES = set()


def log_once(message: str):
    """
    避免未配置可选搜索源时在终端反复刷屏。
    """
    if message in _LOGGED_MESSAGES:
        return

    _LOGGED_MESSAGES.add(message)
    print(message)


def normalize_result(source: str, title: str, url: str, content: str, published_at: str = "", language: str = ""):
    """
    把不同搜索 API 返回的数据，统一成同一种格式。
    这样后面的 Agent 不需要关心结果来自 Tavily、Google 还是 NewsAPI。
    """
    return {
        "source": source,
        "language": language or "",
        "title": title or "",
        "url": url or "",
        "content": content or "",
        "published_at": published_at or "",
        "source_id": "",
        "domain": get_domain(url or "")
    }


def search_tavily(query: str, max_results: int = 5, language: str = "", time_range=None):
    """
    Tavily 搜索：适合 Agent 使用，通常会返回更适合总结的网页摘要内容。
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        log_once("未配置 TAVILY_API_KEY，跳过 Tavily 搜索")
        return []

    client = TavilyClient(api_key=api_key)

    search_params = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic"
    }

    if time_range and time_range.days == 1:
        search_params["time_range"] = "day"
    elif time_range:
        search_params["start_date"] = time_range.start_iso
        search_params["end_date"] = time_range.end_iso

    response = client.search(**search_params)

    results = response.get("results", [])

    return [
        normalize_result(
            source="tavily",
            title=item.get("title"),
            url=item.get("url"),
            content=item.get("content"),
            language=language
        )
        for item in results
    ]


def search_google(query: str, max_results: int = 5, language: str = "", time_range=None):
    """
    Google Custom Search 搜索。

    需要在 .env 中配置：
    GOOGLE_API_KEY=你的 Google API Key
    GOOGLE_CSE_ID=你的搜索引擎 ID
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        log_once("未配置 GOOGLE_API_KEY 或 GOOGLE_CSE_ID，跳过 Google 搜索")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": max_results
    }

    if language == "en":
        params["lr"] = "lang_en"
    elif language == "zh":
        params["lr"] = "lang_zh-CN"

    if time_range:
        params["dateRestrict"] = f"d{time_range.days}"
        params["sort"] = f"date:r:{time_range.start_iso.replace('-', '')}:{time_range.end_iso.replace('-', '')}"

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    items = data.get("items", [])

    return [
        normalize_result(
            source="google",
            title=item.get("title"),
            url=item.get("link"),
            content=item.get("snippet"),
            language=language
        )
        for item in items
    ]


def search_newsapi(query: str, max_results: int = 5, language: str = "", time_range=None):
    """
    NewsAPI 搜索：适合搜索新闻、热点、近期事件。

    需要在 .env 中配置：
    NEWS_API_KEY=你的 NewsAPI Key
    """
    api_key = os.getenv("NEWS_API_KEY")

    if not api_key:
        log_once("未配置 NEWS_API_KEY，跳过 NewsAPI 搜索")
        return []

    url = "https://newsapi.org/v2/everything"
    params = {
        "apiKey": api_key,
        "q": query,
        "pageSize": max_results,
        "sortBy": "relevancy"
    }

    if language == "en":
        params["language"] = "en"

    if time_range:
        params["from"] = time_range.start_iso
        params["to"] = time_range.end_iso

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    articles = data.get("articles", [])

    return [
        normalize_result(
            source="newsapi",
            title=item.get("title"),
            url=item.get("url"),
            content=item.get("description") or item.get("content"),
            published_at=item.get("publishedAt"),
            language=language
        )
        for item in articles
    ]


def search_bing(query: str, max_results: int = 5, language: str = "", time_range=None):
    """
    Bing 搜索预留接口。
    目前先不接入，避免第一版卡在 Azure/Bing 配置上。
    """
    return []


def is_within_time_range(published_at: str, time_range):
    """
    对带发布时间的结果做兜底过滤。
    没有发布时间的通用网页结果保留，因为 Google/Tavily 已在 API 层过滤。
    """
    if not time_range or not published_at:
        return True

    try:
        published_date = datetime.fromisoformat(
            published_at.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return True

    return time_range.start_date <= published_date <= time_range.end_date


def get_domain(url: str):
    """
    从 URL 中提取域名，用于去重。
    """
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def deduplicate_results(results):
    """
    根据 URL 去重。
    如果 URL 完全相同，只保留第一次出现的结果。
    """
    seen_urls = set()
    unique_results = []

    for item in results:
        url = item.get("url", "")

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        unique_results.append(item)

    return unique_results


def add_source_ids(results):
    """
    给每条搜索结果添加引用编号。
    后面 AI 总结时可以使用 [1]、[2]、[3] 这样的来源引用。
    """
    for index, item in enumerate(results, start=1):
        item["source_id"] = index
        item["domain"] = get_domain(item.get("url", ""))

    return results


def get_source_config_issue(source: str):
    """
    返回搜索源无法启用的原因；配置完整时返回 None。
    """
    if source == "tavily" and not os.getenv("TAVILY_API_KEY"):
        return "未配置 TAVILY_API_KEY"

    if source == "google":
        missing = []
        if not os.getenv("GOOGLE_API_KEY"):
            missing.append("GOOGLE_API_KEY")
        if not os.getenv("GOOGLE_CSE_ID"):
            missing.append("GOOGLE_CSE_ID")
        if missing:
            return "未配置 " + " 或 ".join(missing)

    if source == "newsapi" and not os.getenv("NEWS_API_KEY"):
        return "未配置 NEWS_API_KEY"

    return None


def multi_source_search(
    query: str,
    max_results_per_source: int = 5,
    language: str = "",
    time_range=None,
    include_metadata: bool = False
):
    """
    多来源搜索主函数。

    工作流程：
    1. 调用 Tavily
    2. 调用 Google
    3. 调用 NewsAPI
    4. 预留 Bing
    5. 合并搜索结果
    6. 去重
    7. 添加 source_id，方便后续引用
    """
    all_results = []
    enabled_sources = []
    skipped_sources = []
    failed_sources = []

    search_sources = [
        ("tavily", search_tavily),
        ("google", search_google),
        ("newsapi", search_newsapi),
    ]

    for source_name, search_function in search_sources:
        config_issue = get_source_config_issue(source_name)
        if config_issue:
            skipped_sources.append({
                "source": source_name,
                "language": language or "",
                "reason": config_issue
            })
            log_once(f"{config_issue}，跳过 {source_name} 搜索")
            continue

        enabled_sources.append(source_name)

        try:
            results = search_function(
                query,
                max_results=max_results_per_source,
                language=language,
                time_range=time_range
            )
            results = [
                item for item in results
                if is_within_time_range(item.get("published_at", ""), time_range)
            ]
            all_results.extend(results)
        except Exception as error:
            message = f"{source_name} 搜索失败：{error}"
            log_once(message)
            failed_sources.append({
                "source": source_name,
                "language": language or "",
                "reason": str(error)
            })

    unique_results = deduplicate_results(all_results)
    results_with_ids = add_source_ids(unique_results)

    if include_metadata:
        return {
            "results": results_with_ids,
            "enabled_sources": enabled_sources,
            "skipped_sources": skipped_sources,
            "failed_sources": failed_sources
        }

    return results_with_ids


# 保留旧函数名，避免 app.py 或 agent.py 里原来的代码立刻报错。
def search_web(query: str, max_results: int = 5):
    return search_tavily(query, max_results=max_results)
