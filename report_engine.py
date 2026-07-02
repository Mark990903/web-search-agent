from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


CANONICAL_SECTIONS = [
    "Executive Summary",
    "Key Findings",
    "Detailed Analysis",
    "Evidence",
    "References",
    "Future Research",
]
TOC_THRESHOLD = 5
CITATION_PATTERN = re.compile(r"\[\d+\](?:\[\d+\])*")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")


@dataclass
class ResearchReport:
    title: str
    query: str
    planner: dict[str, Any]
    report: str
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
    language: str
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    @property
    def research_id(self) -> str:
        research_id = self.metadata.get("research_id")
        if research_id:
            return str(research_id)
        research_id = generate_research_id(self.created_at)
        self.metadata["research_id"] = research_id
        return research_id

    def to_markdown(self) -> str:
        return render_markdown(self)

    def export_word(self, *_args: Any, **_kwargs: Any) -> None:
        """Reserved Word export interface for a later version."""
        raise NotImplementedError("Word export is not implemented yet.")


def generate_research_id(created_at: datetime | None = None) -> str:
    timestamp = created_at or datetime.now().astimezone()
    return f"RPT-{timestamp:%Y%m%d-%H%M%S}"


def create_research_report(
    *,
    title: str = "Research Report",
    query: str,
    planner: dict[str, Any] | None,
    report: str,
    sources: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None = None,
    language: str = "zh",
    created_at: datetime | None = None,
) -> ResearchReport:
    created = created_at or datetime.now().astimezone()
    report_metadata = dict(metadata or {})
    report_metadata.setdefault("research_id", generate_research_id(created))
    report_metadata.setdefault("generated_at", format_datetime(created))
    report_metadata.setdefault("language", language)
    report_metadata.setdefault("total_sources", len(sources or []))

    return ResearchReport(
        title=title,
        query=query,
        planner=planner or {},
        report=report or "",
        sources=sources or [],
        metadata=report_metadata,
        language=language,
        created_at=created,
    )


def render_markdown(report: ResearchReport) -> str:
    body = report.report.strip()
    sections = extract_report_sections(body)
    lines = [f"# {report.title}", ""]
    lines.extend(render_metadata(report))
    lines.append("")

    if should_include_toc(CANONICAL_SECTIONS):
        lines.extend(render_table_of_contents(CANONICAL_SECTIONS))
        lines.append("")

    lines.extend(
        [
            "## Executive Summary",
            "",
            build_executive_summary(body, sections),
            "",
            "## Key Findings",
            "",
            build_key_findings(body, sections),
            "",
            "## Detailed Analysis",
            "",
            build_detailed_analysis(report, body, sections),
            "",
            "## Evidence",
            "",
            build_evidence(body, report.sources),
            "",
            "## References",
            "",
            build_references(report.sources),
            "",
            "## Future Research",
            "",
            build_future_research(report, sections),
        ]
    )

    return "\n".join(lines).strip() + "\n"


def should_include_toc(section_names: list[str]) -> bool:
    return len(section_names) > TOC_THRESHOLD


def render_table_of_contents(section_names: list[str]) -> list[str]:
    lines = ["## Table of Contents", ""]
    lines.extend(
        f"{index} {section}" for index, section in enumerate(section_names, start=1)
    )
    return lines


def render_metadata(report: ResearchReport) -> list[str]:
    metadata = report.metadata
    research_time = metadata.get("research_time") or metadata.get("generated_at")
    generated_at = metadata.get("generated_at") or format_datetime(report.created_at)
    search_sources = metadata.get("search_sources") or []
    if isinstance(search_sources, str):
        source_text = search_sources
    else:
        source_text = ", ".join(str(item) for item in search_sources) or "None"

    planner_enabled = bool(report.planner.get("enabled"))
    time_range = metadata.get("time_range") or "None"
    search_duration = metadata.get("search_duration")
    if isinstance(search_duration, (int, float)):
        search_duration_text = f"{search_duration:.2f}s"
    else:
        search_duration_text = str(search_duration or "N/A")

    rows = [
        ("Research ID", report.research_id),
        ("Research Time", research_time or "N/A"),
        ("Generated At", generated_at),
        ("Language", metadata.get("language") or report.language),
        ("Search Sources", source_text),
        ("Total Sources", metadata.get("total_sources", len(report.sources))),
        ("Planner", "Enabled" if planner_enabled else "Disabled"),
        ("Time Range", time_range),
        ("Search Duration", search_duration_text),
    ]

    lines = ["## Research Metadata", ""]
    lines.extend(f"- **{label}:** {value}" for label, value in rows)
    return lines


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M %Z").strip()


def extract_report_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading = ""

    for line in markdown.splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.*)\s*$", line)
        if heading_match:
            current_heading = normalize_heading(heading_match.group(1))
            sections.setdefault(current_heading, [])
            continue
        if current_heading:
            sections.setdefault(current_heading, []).append(line)

    return {
        heading: "\n".join(lines).strip()
        for heading, lines in sections.items()
        if "\n".join(lines).strip()
    }


def normalize_heading(heading: str) -> str:
    heading = re.sub(r"^\d+[\.\)、\s]+", "", heading.strip())
    return heading.lower()


def first_matching_section(
    sections: dict[str, str],
    keywords: list[str],
) -> str:
    for heading, content in sections.items():
        if any(keyword.lower() in heading for keyword in keywords):
            return content
    return ""


def build_executive_summary(markdown: str, sections: dict[str, str]) -> str:
    summary = first_matching_section(
        sections,
        ["executive summary", "one-sentence", "一句话", "研究主题", "核心结论"],
    )
    candidate = first_meaningful_sentence(summary or markdown)
    return candidate or "当前报告未生成可用的一句话总结。"


def build_key_findings(markdown: str, sections: dict[str, str]) -> str:
    findings = first_matching_section(
        sections,
        ["key findings", "核心发现", "核心结论"],
    )
    lines = extract_bullets(findings) or extract_cited_lines(markdown)[:5]
    if not lines:
        summary = first_meaningful_sentence(markdown)
        lines = [summary] if summary else ["当前报告未生成明确的核心发现。"]
    return "\n".join(f"- {strip_bullet_prefix(line)}" for line in lines[:8])


def build_detailed_analysis(
    report: ResearchReport,
    markdown: str,
    sections: dict[str, str],
) -> str:
    analysis = first_matching_section(
        sections,
        ["detailed analysis", "分主题分析", "详细分析"],
    )
    planner_sub_queries = report.planner.get("sub_queries") or []

    if planner_sub_queries:
        blocks = []
        for index, item in enumerate(planner_sub_queries, start=1):
            title = item.get("title") or f"Sub-question {index}"
            purpose = item.get("purpose") or ""
            query_zh = item.get("query_zh") or ""
            query_en = item.get("query_en") or ""
            subsection = extract_subsection_by_title(markdown, title)
            subsection = subsection or extract_subsection_by_title(analysis, title)
            blocks.append(
                "\n".join(
                    line
                    for line in [
                        f"### {index}. {title}",
                        f"- Query ZH: {query_zh}" if query_zh else "",
                        f"- Query EN: {query_en}" if query_en else "",
                        f"- Purpose: {purpose}" if purpose else "",
                        "",
                        subsection or "当前报告未单独生成该子问题的详细分析。",
                    ]
                    if line != ""
                )
            )
        return "\n\n".join(blocks)

    return analysis or fallback_analysis(markdown)


def extract_subsection_by_title(markdown: str, title: str) -> str:
    if not markdown or not title:
        return ""

    title_key = normalize_title_key(title)
    lines = markdown.splitlines()
    start_index: int | None = None
    start_level = 0

    for index, line in enumerate(lines):
        heading_match = re.match(r"^\s{0,3}(#{1,6})\s+(.*)\s*$", line)
        if not heading_match:
            continue

        heading_title = normalize_title_key(heading_match.group(2))
        if title_key and title_key in heading_title:
            start_index = index + 1
            start_level = len(heading_match.group(1))
            break

    if start_index is None:
        return ""

    collected = []
    for line in lines[start_index:]:
        heading_match = re.match(r"^\s{0,3}(#{1,6})\s+(.*)\s*$", line)
        if heading_match and len(heading_match.group(1)) <= start_level:
            break
        collected.append(line)

    return "\n".join(collected).strip()


def normalize_title_key(value: Any) -> str:
    text = normalize_heading(str(value))
    text = re.sub(r"[\s：:，,。.!！?？\-_/]+", "", text)
    return text


def build_evidence(markdown: str, sources: list[dict[str, Any]]) -> str:
    cited_lines = extract_cited_lines(markdown)
    if cited_lines:
        return "\n".join(f"- {line}" for line in cited_lines[:10])

    source_lines = []
    for item in sources[:10]:
        source_id = item.get("source_id", "")
        title = item.get("title") or "Untitled source"
        content = normalize_whitespace(item.get("content") or "")
        if content:
            source_lines.append(f"- [{source_id}] {title}: {content[:220]}")
    return "\n".join(source_lines) or "- 当前报告未生成可用证据摘录。"


def build_references(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "- No sources available."

    lines = []
    for item in sources:
        source_id = item.get("source_id", "")
        title = normalize_whitespace(item.get("title") or "Untitled source")
        url = item.get("url") or ""
        source = item.get("source") or "source"
        lines.append(f"- [{source_id}] {title} ({source}) - {url}")
    return "\n".join(lines)


def build_future_research(report: ResearchReport, sections: dict[str, str]) -> str:
    future = first_matching_section(
        sections,
        ["future research", "后续研究", "follow-up"],
    )
    bullets = extract_bullets(future)
    if bullets:
        return "\n".join(f"- {strip_bullet_prefix(line)}" for line in bullets[:5])

    planner_sub_queries = report.planner.get("sub_queries") or []
    if planner_sub_queries:
        questions = [
            f"继续跟踪“{item.get('title', f'子问题 {index}')}”的最新证据。"
            for index, item in enumerate(planner_sub_queries[:3], start=1)
        ]
    else:
        questions = [
            f"继续跟踪“{report.query}”的最新来源与数据变化。",
            "补充更多一手资料、行业报告或官方统计。",
            "对关键结论进行跨来源复核。",
        ]
    return "\n".join(f"- {question}" for question in questions)


def fallback_analysis(markdown: str) -> str:
    cleaned = demote_embedded_headings(strip_markdown_title(markdown)).strip()
    return cleaned or "当前报告未生成详细分析。"


def strip_markdown_title(markdown: str) -> str:
    lines = [
        line
        for line in markdown.splitlines()
        if not re.match(r"^\s{0,3}#\s+", line)
    ]
    return "\n".join(lines)


def demote_embedded_headings(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.*)\s*$", line)
        if heading_match:
            heading = re.sub(r"^\d+[\.\)、\s]+", "", heading_match.group(1)).strip()
            lines.append(f"**{heading}**")
        else:
            lines.append(line)
    return "\n".join(lines)


def first_meaningful_sentence(markdown: str) -> str:
    text = strip_markdown_syntax(markdown)
    for part in re.split(r"(?<=[。！？.!?])\s+", text):
        candidate = part.strip()
        if candidate:
            return candidate
    return text[:240].strip()


def strip_markdown_syntax(markdown: str) -> str:
    text = MARKDOWN_LINK_PATTERN.sub(r"\1", markdown)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[\.\)]\s+", "", text, flags=re.MULTILINE)
    return normalize_whitespace(text)


def extract_bullets(markdown: str) -> list[str]:
    bullets = []
    for line in markdown.splitlines():
        if re.match(r"^\s*(?:[-*+]|\d+[\.\)])\s+", line):
            bullets.append(strip_bullet_prefix(line))
    return bullets


def strip_bullet_prefix(line: str) -> str:
    return re.sub(r"^\s*(?:[-*+]|\d+[\.\)])\s+", "", line).strip()


def extract_cited_lines(markdown: str) -> list[str]:
    lines = []
    for line in markdown.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if CITATION_PATTERN.search(cleaned):
            lines.append(strip_bullet_prefix(cleaned))
    return lines


def normalize_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()
