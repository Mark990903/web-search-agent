import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

logger = logging.getLogger(__name__)
_LOGGED_MESSAGES: set[str] = set()

SearchResult = dict[str, Any]
SearchPayload = dict[str, Any]
SearchFunction = Callable[..., list[SearchResult]]


def log_once(level: int, message: str) -> None:
    """Log the same operational message only once.

    Args:
        level: Standard logging level, such as logging.WARNING.
        message: Message to log.
    """
    if message in _LOGGED_MESSAGES:
        return

    _LOGGED_MESSAGES.add(message)
    logger.log(level, message)


def get_domain(url: str) -> str:
    """Extract a normalized domain from a URL.

    Args:
        url: URL string.

    Returns:
        Domain without leading www, or an empty string when parsing fails.
    """
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def normalize_result(
    source: str,
    title: str | None,
    url: str | None,
    content: str | None,
    published_at: str | None = "",
    language: str = "",
) -> SearchResult:
    """Normalize one provider result into the shared Agent schema.

    Args:
        source: Search engine name, such as tavily, google, or newsapi.
        title: Result title.
        url: Result URL.
        content: Result summary or content snippet.
        published_at: Optional publication timestamp.
        language: Search language label, usually zh or en.

    Returns:
        A normalized search result dictionary.
    """
    return {
        "source": source,
        "language": language or "",
        "title": title or "",
        "url": url or "",
        "content": content or "",
        "published_at": published_at or "",
        "source_id": "",
        "domain": get_domain(url or ""),
    }


def search_tavily(
    query: str,
    max_results: int = 5,
    language: str = "",
    time_range: Any = None,
) -> list[SearchResult]:
    """Search Tavily and return normalized results.

    Args:
        query: Search query.
        max_results: Maximum results to request.
        language: Search language label.
        time_range: Optional TimeRange detected from the user query.

    Returns:
        Normalized Tavily results. Returns an empty list when not configured.
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        log_once(logging.WARNING, "未配置 TAVILY_API_KEY，跳过 Tavily 搜索")
        return []

    client = TavilyClient(api_key=api_key)
    search_params: dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
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
            language=language,
        )
        for item in results
    ]


def build_serper_payload(
    query: str,
    max_results: int,
    language: str,
    time_range: Any = None,
) -> dict[str, Any]:
    """Build the Serper request payload for Google search.

    Args:
        query: Search query.
        max_results: Maximum results to request.
        language: Search language label.
        time_range: Optional TimeRange detected from the user query.

    Returns:
        JSON payload for Serper.
    """
    search_query = query
    if time_range:
        search_query = (
            f"{search_query} after:{time_range.start_iso} "
            f"before:{time_range.end_iso}"
        )

    payload: dict[str, Any] = {
        "q": search_query,
        "num": max_results,
    }

    if language == "en":
        payload["hl"] = "en"
        payload["gl"] = "us"
    elif language == "zh":
        payload["hl"] = "zh-cn"

    return payload


def search_google(
    query: str,
    max_results: int = 5,
    language: str = "",
    time_range: Any = None,
) -> list[SearchResult]:
    """Search Google through the configured provider.

    The current implementation uses Serper API as the Google search provider.

    Args:
        query: Search query.
        max_results: Maximum results to request.
        language: Search language label.
        time_range: Optional TimeRange detected from the user query.

    Returns:
        Normalized Google results. Returns an empty list when not configured.
    """
    api_key = os.getenv("SERPER_API_KEY")

    if not api_key:
        log_once(logging.WARNING, "未配置 SERPER_API_KEY，跳过 Google/Serper 搜索")
        return []

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = build_serper_payload(
        query=query,
        max_results=max_results,
        language=language,
        time_range=time_range,
    )

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        log_once(logging.ERROR, f"Google/Serper 搜索失败：{error}")
        return []

    data = response.json()
    items = data.get("organic", [])

    return [
        normalize_result(
            source="google",
            title=item.get("title"),
            url=item.get("link"),
            content=item.get("snippet"),
            language=language,
        )
        for item in items
    ]


def search_newsapi(
    query: str,
    max_results: int = 5,
    language: str = "",
    time_range: Any = None,
) -> list[SearchResult]:
    """Search NewsAPI and return normalized results.

    Args:
        query: Search query.
        max_results: Maximum results to request.
        language: Search language label. English searches pass language="en";
            Chinese searches intentionally do not force language="zh".
        time_range: Optional TimeRange detected from the user query.

    Returns:
        Normalized NewsAPI results. Returns an empty list when not configured.
    """
    api_key = os.getenv("NEWS_API_KEY")

    if not api_key:
        log_once(logging.WARNING, "未配置 NEWS_API_KEY，跳过 NewsAPI 搜索")
        return []

    url = "https://newsapi.org/v2/everything"
    params: dict[str, Any] = {
        "apiKey": api_key,
        "q": query,
        "pageSize": max_results,
        "sortBy": "relevancy",
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
            language=language,
        )
        for item in articles
    ]


def search_bing(
    query: str,
    max_results: int = 5,
    language: str = "",
    time_range: Any = None,
) -> list[SearchResult]:
    """Reserved Bing search adapter.

    Args:
        query: Search query.
        max_results: Maximum results to request.
        language: Search language label.
        time_range: Optional TimeRange detected from the user query.

    Returns:
        Empty list because Bing is not enabled in V2.2.
    """
    return []


def is_within_time_range(published_at: str, time_range: Any) -> bool:
    """Return whether a result timestamp is inside the requested range.

    Args:
        published_at: Publication timestamp from a search provider.
        time_range: Optional TimeRange detected from the user query.

    Returns:
        True when the result is in range or cannot be safely filtered.
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


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Deduplicate normalized results by URL while preserving order.

    Args:
        results: Normalized result list.

    Returns:
        Deduplicated result list.
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


def add_source_ids(results: list[SearchResult]) -> list[SearchResult]:
    """Add stable source IDs and domains to search results.

    Args:
        results: Normalized result list.

    Returns:
        The same list with source_id and domain populated.
    """
    for index, item in enumerate(results, start=1):
        item["source_id"] = index
        item["domain"] = get_domain(item.get("url", ""))

    return results


def merge_results(results: list[SearchResult]) -> list[SearchResult]:
    """Merge, deduplicate, and number normalized results.

    Args:
        results: Result list from one or more search providers.

    Returns:
        Deduplicated results with source IDs.
    """
    return add_source_ids(deduplicate_results(results))


def get_source_config_issue(source: str) -> str | None:
    """Return a human-readable configuration issue for a source.

    Args:
        source: Search source name.

    Returns:
        Reason text when the source is not configured, otherwise None.
    """
    if source == "tavily" and not os.getenv("TAVILY_API_KEY"):
        return "未配置 TAVILY_API_KEY"

    if source == "google" and not os.getenv("SERPER_API_KEY"):
        return "未配置 SERPER_API_KEY"

    if source == "newsapi" and not os.getenv("NEWS_API_KEY"):
        return "未配置 NEWS_API_KEY"

    return None


def multi_source_search(
    query: str,
    max_results_per_source: int = 5,
    language: str = "",
    time_range: Any = None,
    include_metadata: bool = False,
) -> list[SearchResult] | SearchPayload:
    """Run all configured search providers and merge their results.

    Args:
        query: Search query.
        max_results_per_source: Maximum result count for each provider.
        language: Search language label.
        time_range: Optional TimeRange detected from the user query.
        include_metadata: Whether to return enabled/skipped/failed sources.

    Returns:
        A result list by default. When include_metadata is True, returns a
        payload containing results and source status metadata.
    """
    start_time = time.perf_counter()
    logger.info("开始搜索 query=%s language=%s", query, language or "unknown")

    all_results: list[SearchResult] = []
    enabled_sources: list[str] = []
    skipped_sources: list[dict[str, str]] = []
    failed_sources: list[dict[str, str]] = []

    search_sources: list[tuple[str, SearchFunction]] = [
        ("tavily", search_tavily),
        ("google", search_google),
        ("newsapi", search_newsapi),
    ]

    for source_name, search_function in search_sources:
        config_issue = get_source_config_issue(source_name)
        if config_issue:
            skipped_sources.append(
                {
                    "source": source_name,
                    "language": language or "",
                    "reason": config_issue,
                }
            )
            log_once(logging.WARNING, f"{config_issue}，跳过 {source_name} 搜索")
            continue

        enabled_sources.append(source_name)

        try:
            results = search_function(
                query,
                max_results=max_results_per_source,
                language=language,
                time_range=time_range,
            )
            filtered_results = [
                item
                for item in results
                if is_within_time_range(item.get("published_at", ""), time_range)
            ]
            all_results.extend(filtered_results)
        except Exception as error:
            message = f"{source_name} 搜索失败：{error}"
            log_once(logging.ERROR, message)
            failed_sources.append(
                {
                    "source": source_name,
                    "language": language or "",
                    "reason": str(error),
                }
            )

    results_with_ids = merge_results(all_results)
    elapsed = time.perf_counter() - start_time
    logger.info(
        "搜索完成 query=%s language=%s results=%s elapsed=%.2fs",
        query,
        language or "unknown",
        len(results_with_ids),
        elapsed,
    )

    if include_metadata:
        return {
            "results": results_with_ids,
            "enabled_sources": enabled_sources,
            "skipped_sources": skipped_sources,
            "failed_sources": failed_sources,
        }

    return results_with_ids


def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """Backward-compatible wrapper for Tavily search."""
    return search_tavily(query, max_results=max_results)
