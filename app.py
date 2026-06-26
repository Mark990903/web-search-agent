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

            report = summarize_search(query)

        # 展示 AI 自动生成的英文搜索关键词
        st.caption(
            f"English Search Query: {report.get('english_query', '')}"
        )

        time_range = report.get("time_range")
        if time_range:
            st.caption(
                f"时间范围：{time_range['label']}（{time_range['start_date']} 至 {time_range['end_date']}）"
            )

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
