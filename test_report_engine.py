from datetime import datetime, timezone

from pdf_export import export_report_to_pdf
from report_engine import (
    ResearchReport,
    create_research_report,
    generate_research_id,
    should_include_toc,
)


def make_report() -> ResearchReport:
    created_at = datetime(2026, 6, 27, 14, 30, 15, tzinfo=timezone.utc)
    return create_research_report(
        query="AI Agent 市场现状",
        planner={
            "enabled": True,
            "sub_queries": [
                {
                    "title": "主要公司",
                    "query_zh": "AI Agent 主要公司 2026",
                    "query_en": "AI Agent companies 2026",
                    "purpose": "识别市场参与者",
                }
            ],
        },
        report=(
            "# Web Search Agent V3 Research Report\n\n"
            "## 核心结论\n"
            "- AI Agent 市场正在加速发展。[1]\n\n"
            "## 分主题分析\n"
            "主要公司正在围绕企业工作流构建产品。[1]\n\n"
            "## 后续研究建议\n"
            "- 继续跟踪融资和客户案例。"
        ),
        sources=[
            {
                "source_id": 1,
                "source": "tavily",
                "title": "AI Agent Market",
                "url": "https://example.com/agent",
                "content": "Market evidence",
            }
        ],
        metadata={
            "search_sources": ["tavily"],
            "time_range": "None",
            "search_duration": 1.25,
        },
        language="zh",
        created_at=created_at,
    )


def test_research_report_creation_adds_research_id():
    report = make_report()

    assert isinstance(report, ResearchReport)
    assert report.query == "AI Agent 市场现状"
    assert report.research_id == "RPT-20260627-143015"


def test_markdown_uses_unified_template():
    markdown = make_report().to_markdown()

    assert markdown.startswith("# Research Report")
    assert "## Executive Summary" in markdown
    assert "## Key Findings" in markdown
    assert "## Detailed Analysis" in markdown
    assert "## Evidence" in markdown
    assert "## References" in markdown
    assert "## Future Research" in markdown
    assert "AI Agent 市场正在加速发展。[1]" in markdown


def test_table_of_contents_is_generated_for_canonical_sections():
    markdown = make_report().to_markdown()

    assert should_include_toc(
        [
            "Executive Summary",
            "Key Findings",
            "Detailed Analysis",
            "Evidence",
            "References",
            "Future Research",
        ]
    )
    assert "## Table of Contents" in markdown
    assert "1 Executive Summary" in markdown
    assert "6 Future Research" in markdown


def test_metadata_is_rendered():
    markdown = make_report().to_markdown()

    assert "## Research Metadata" in markdown
    assert "**Research ID:** RPT-20260627-143015" in markdown
    assert "**Planner:** Enabled" in markdown
    assert "**Search Sources:** tavily" in markdown
    assert "**Total Sources:** 1" in markdown


def test_generate_research_id_format():
    created_at = datetime(2026, 6, 27, 14, 30, 15, tzinfo=timezone.utc)

    assert generate_research_id(created_at) == "RPT-20260627-143015"


def test_pdf_export_returns_pdf_bytes(tmp_path):
    output_path = tmp_path / "Research_Report.pdf"
    pdf_bytes = export_report_to_pdf(make_report(), output_path=output_path)

    assert pdf_bytes.startswith(b"%PDF")
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
