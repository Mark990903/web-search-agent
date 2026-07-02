import logging
from typing import Any

import streamlit as st

from agent import summarize_search
from pdf_export import export_report_to_pdf


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

st.title("网页搜索总结 Agent")


def display_source_status(report: dict[str, Any]) -> None:
    """Display source status and statistics above the report.

    Args:
        report: Structured payload returned by summarize_search().
    """
    enabled_sources = report.get("enabled_sources", [])
    skipped_sources = report.get("skipped_sources", [])
    failed_sources = report.get("failed_sources", [])
    source_stats = report.get("source_stats", {})

    st.subheader("搜索源状态")

    if enabled_sources:
        st.write("已启用搜索源：" + "、".join(enabled_sources))
    else:
        st.write("已启用搜索源：暂无")

    if skipped_sources:
        st.write("已跳过搜索源")
        skipped_source_rows = [
            {
                "搜索源": item.get("source", ""),
                "语言": item.get("language", ""),
                "跳过原因": item.get("reason", ""),
            }
            for item in skipped_sources
        ]
        st.dataframe(skipped_source_rows, width="stretch")
    else:
        st.write("已跳过搜索源：无")

    if failed_sources:
        st.error("部分搜索源失败，报告已基于可用来源继续生成。")
        failed_source_rows = [
            {
                "搜索源": item.get("source", ""),
                "语言": item.get("language", ""),
                "失败原因": item.get("reason", ""),
            }
            for item in failed_sources
        ]
        st.dataframe(failed_source_rows, width="stretch")

    st.subheader("来源统计")
    col_total, col_engine, col_language = st.columns(3)
    col_total.metric("总来源数", source_stats.get("total_sources", 0))
    col_engine.write("按搜索源")
    col_engine.json(source_stats.get("by_engine", {}))
    col_language.write("按语言")
    col_language.json(source_stats.get("by_language", {}))


def display_query_planner(report: dict[str, Any]) -> None:
    """Display optional Query Planner metadata without taking over the page."""
    planner = report.get("planner", {})

    with st.expander("Query Planner", expanded=False):
        if not planner.get("enabled"):
            st.write("Query Planner：未启用")
            return

        planner_error = planner.get("planner_error") or report.get("planner_error")
        if planner_error:
            st.warning("Query Planner 失败，已回退到普通搜索。")
            st.caption(planner_error)

        if planner.get("is_research_task"):
            st.write("Planner 判断结果：研究任务")
            sub_query_rows = [
                {
                    "title": item.get("title", ""),
                    "query_zh": item.get("query_zh", ""),
                    "query_en": item.get("query_en", ""),
                    "purpose": item.get("purpose", ""),
                }
                for item in planner.get("sub_queries", [])
            ]
            if sub_query_rows:
                st.dataframe(sub_query_rows, width="stretch")
        else:
            st.write("Planner 判断结果：普通搜索")


def display_report_actions(markdown: str) -> None:
    """Display V3.2 report actions for the current in-memory report."""
    st.subheader("Report Actions")
    col_md, col_pdf, col_copy = st.columns(3)

    col_md.download_button(
        "Download Markdown",
        data=markdown,
        file_name="Research_Report.md",
        mime="text/markdown",
    )

    pdf_bytes = export_report_to_pdf(markdown)
    col_pdf.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="Research_Report.pdf",
        mime="application/pdf",
    )

    if col_copy.button("Copy Markdown"):
        st.session_state["show_markdown_copy"] = True

    if st.session_state.get("show_markdown_copy"):
        st.text_area(
            "Markdown",
            value=markdown,
            height=260,
            key="markdown_copy_text",
        )


# 输入框
# 用户输入想搜索的话题
query = st.text_input("请输入搜索主题")
use_planner = st.checkbox("启用 Query Planner", value=True)


# 点击按钮后执行
if st.button("开始搜索"):

    # 判断用户是否输入内容
    if not query:

        # 页面弹出警告
        st.warning("请输入搜索主题")

    else:

        # 显示当前搜索内容
        st.write(f"你搜索的是：{query}")

        # 显示加载动画
        # 此时 Agent 正在：
        # 中文搜索 → 英文搜索 → 多来源融合 → 双语报告生成
        with st.spinner("Agent 正在进行中英文双语搜索并生成报告..."):

            try:
                report = summarize_search(query, use_planner=use_planner)
            except Exception as error:
                report = {
                    "chinese": f"Agent 运行失败：{error}",
                    "english": f"Agent failed: {error}",
                    "english_query": "",
                    "time_range": None,
                    "sources": [],
                    "source_stats": {
                        "total_sources": 0,
                        "by_engine": {},
                        "by_language": {},
                    },
                    "enabled_sources": [],
                    "skipped_sources": [],
                    "failed_sources": [],
                    "planner": {
                        "enabled": use_planner,
                        "is_research_task": False,
                        "main_topic": query,
                        "sub_queries": [],
                        "planner_error": str(error),
                    },
                    "planner_error": str(error),
                    "error": str(error),
                }
                logger.error("Agent 运行失败：%s", error)

        st.session_state["latest_report"] = report
        st.session_state["show_markdown_copy"] = False


report = st.session_state.get("latest_report")

if report:
    # 展示 AI 自动生成的英文搜索关键词
    st.caption(
        f"English Search Query: {report.get('english_query', '')}"
    )

    time_range = report.get("time_range")
    if time_range:
        st.caption(
            "时间范围："
            f"{time_range['label']}"
            f"（{time_range['start_date']} 至 {time_range['end_date']}）"
        )

    display_query_planner(report)
    display_source_status(report)

    if report.get("error"):
        st.error(report["error"])

    # 中英文报告切换
    report_language = st.radio(
        "报告语言",
        ["中文", "English"],
        horizontal=True,
    )

    st.subheader("总结报告")

    if report_language == "中文":
        current_markdown = report.get("research_report_markdown") or report["chinese"]
        st.markdown(current_markdown)
        display_report_actions(current_markdown)
    else:
        if not report.get("english_report_available", True):
            st.info("English report is not generated by default in V2.2 stable.")
        st.markdown(report["english"])
