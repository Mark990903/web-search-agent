# 导入 Streamlit
# 用于快速构建 Web 页面
import streamlit as st

# 导入 Agent 主函数
# summarize_search() 内部会完成：
# 1. 自动翻译英文 Query
# 2. 中文搜索
# 3. 英文搜索
# 4. 多来源融合
# 5. 生成中文报告
# 6. 生成英文报告
from agent import summarize_search


# 页面标题
st.title("网页搜索总结 Agent")


def display_source_status(report):
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
                "跳过原因": item.get("reason", "")
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
                "失败原因": item.get("reason", "")
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


# 输入框
# 用户输入想搜索的话题
query = st.text_input("请输入搜索主题")


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
                report = summarize_search(query)
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
                        "by_language": {}
                    },
                    "enabled_sources": [],
                    "skipped_sources": [],
                    "failed_sources": [],
                    "error": str(error)
                }

        # 展示 AI 自动生成的英文搜索关键词
        st.caption(
            f"English Search Query: {report.get('english_query', '')}"
        )

        time_range = report.get("time_range")
        if time_range:
            st.caption(
                f"时间范围：{time_range['label']}（{time_range['start_date']} 至 {time_range['end_date']}）"
            )

        display_source_status(report)

        if report.get("error"):
            st.error(report["error"])

        # 中英文报告切换
        report_language = st.radio(
            "报告语言",
            ["中文", "English"],
            horizontal=True
        )

        st.subheader("总结报告")

        if report_language == "中文":
            st.markdown(report["chinese"])
        else:
            st.markdown(report["english"])
