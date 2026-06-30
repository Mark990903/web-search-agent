import re
from typing import Any


CITATION_PATTERN = re.compile(r"(?<!\[)\[(\d+)\](?!\]\()")
REFERENCE_HEADING_PATTERN = re.compile(
    r"^\s{0,3}#{0,6}\s*(?:\d+\.\s*)?(?:参考来源|references?)\s*$",
    re.IGNORECASE,
)


def extract_citations(report: str) -> list[int]:
    """Extract unique numeric citation IDs from a report."""
    citations: list[int] = []
    seen: set[int] = set()

    for match in CITATION_PATTERN.finditer(report):
        source_id = int(match.group(1))
        if source_id in seen:
            continue
        seen.add(source_id)
        citations.append(source_id)

    return citations


def remove_invalid_citations(report: str, valid_source_ids: set[int]) -> str:
    """Remove citation markers that do not map to known source IDs."""

    def replace(match: re.Match[str]) -> str:
        source_id = int(match.group(1))
        if source_id in valid_source_ids:
            return match.group(0)
        return ""

    return CITATION_PATTERN.sub(replace, report)


def split_reference_section(report: str) -> tuple[str, str]:
    """Split report body from the references section, if one exists."""
    lines = report.splitlines(keepends=True)

    for index, line in enumerate(lines):
        if REFERENCE_HEADING_PATTERN.match(line.strip()):
            return "".join(lines[:index]), "".join(lines[index:])

    return report, ""


def build_source_url_map(sources: list[dict[str, Any]]) -> dict[int, str]:
    """Build a source_id to URL map from normalized source dictionaries."""
    source_urls: dict[int, str] = {}

    for item in sources:
        try:
            source_id = int(item.get("source_id"))
        except (TypeError, ValueError):
            continue

        url = str(item.get("url") or "").strip()
        if url:
            source_urls[source_id] = url

    return source_urls


def convert_citations_to_links(report: str, sources: list[dict[str, Any]]) -> str:
    """Convert valid citation markers in report body to Markdown links."""
    body, references = split_reference_section(report)
    source_urls = build_source_url_map(sources)

    def replace(match: re.Match[str]) -> str:
        source_id = int(match.group(1))
        url = source_urls.get(source_id)
        if not url:
            return match.group(0)
        return f"[[{source_id}]]({url})"

    return CITATION_PATTERN.sub(replace, body) + references


def process_report_citations(report: str, sources: list[dict[str, Any]]) -> str:
    """Remove invalid citations and convert valid body citations to links."""
    valid_source_ids = {
        source_id
        for source_id in build_source_url_map(sources).keys()
    }

    for item in sources:
        try:
            valid_source_ids.add(int(item.get("source_id")))
        except (TypeError, ValueError):
            continue

    cleaned_report = remove_invalid_citations(report, valid_source_ids)
    return convert_citations_to_links(cleaned_report, sources)
