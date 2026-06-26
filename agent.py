# 导入操作系统模块
# 用于读取环境变量（.env中的配置）
import os

# 导入 dotenv
# 用于自动加载 .env 文件中的配置
from dotenv import load_dotenv

# 导入 OpenAI SDK
# 虽然这里连接的是 OFOX 接口，但 OFOX 提供的是 OpenAI 兼容格式
from openai import OpenAI

# 导入我们自己编写的多来源搜索工具
# multi_source_search() 会同时调用 Tavily、Google、NewsAPI 等搜索来源
from search_tool import multi_source_search, deduplicate_results, add_source_ids
from time_awareness import detect_time_range, describe_time_range


# 加载 .env 文件
# 执行后即可通过 os.getenv() 获取配置项
load_dotenv()


def create_llm_client():
    """
    创建 OFOX 的 OpenAI 兼容客户端。
    后面翻译、中文报告、英文报告都会复用这个客户端。
    """
    return OpenAI(
        api_key=os.getenv("OFOX_API_KEY"),
        base_url=os.getenv("OFOX_BASE_URL")
    )


def translate_query_to_english(query: str):
    """
    将用户输入的中文搜索问题翻译成简洁的英文搜索关键词。
    这样可以同时搜索中文互联网和英文互联网，提升资料来源多样性。
    """
    client = create_llm_client()

    response = client.chat.completions.create(
        model=os.getenv("OFOX_MODEL"),
        messages=[
            {
                "role": "system",
                "content": "Translate the user's query into concise English search keywords only. Do not explain."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def build_context(results):
    """
    将多来源搜索结果整理成大模型更容易理解的文本格式。

    每条资料都会带有 source_id。
    大模型在生成报告时，可以用 [1]、[2]、[3] 这样的格式引用来源。

    参数:
        results: 多来源搜索结果列表

    返回:
        context: 拼接后的长文本
    """

    context = ""

    for item in results:
        source_id = item.get("source_id", "")
        source = item.get("source", "")
        language = item.get("language", "")
        title = item.get("title", "")
        url = item.get("url", "")
        domain = item.get("domain", "")
        published_at = item.get("published_at", "")
        content = item.get("content", "")

        context += f"""
来源编号：[{source_id}]
搜索来源：{source}
搜索语言：{language}
网站域名：{domain}
发布时间：{published_at}
标题：{title}
链接：{url}
内容摘要：{content}
"""

    return context


def generate_report(query: str, english_query: str, context: str, report_language: str, time_range=None):
    """
    根据同一批双语搜索资料生成指定语言的研究报告。

    参数:
        query: 用户原始输入
        english_query: 自动翻译后的英文搜索关键词
        context: 已整理好的搜索资料
        report_language: "zh" 或 "en"
    """
    client = create_llm_client()

    if report_language == "zh":
        language_instruction = "请生成中文研究报告。"
        title = "# Web Search Agent V2 研究报告"
        section_names = """
## 1. 一句话结论
用一句话总结这个主题的核心结论，并添加来源引用。

## 2. 核心发现
用 3-5 条 bullet points 总结，每条都必须带来源引用。

## 3. 详细分析
分段展开说明，重要判断必须带来源引用。

## 4. 多来源交叉验证
说明哪些信息被多个来源共同支持，哪些信息只来自单一来源。

## 5. 信息缺口与不确定性
说明当前资料中没有覆盖、证据不足或需要继续搜索的地方。

## 6. 参考来源
按照下面格式列出所有使用到的来源：
[来源编号] 标题 - 链接

## 7. 后续可继续搜索的问题
列出 3 个适合继续搜索的问题。
"""
    else:
        language_instruction = "Please generate the research report in English."
        title = "# Web Search Agent V2 Research Report"
        section_names = """
## 1. One-sentence conclusion
Summarize the core conclusion in one sentence and include source citations.

## 2. Key findings
Summarize 3-5 key findings. Every bullet point must include source citations.

## 3. Detailed analysis
Explain the topic in clear sections. Important claims must include source citations.

## 4. Cross-source verification
Explain which points are supported by multiple sources and which points come from a single source only.

## 5. Information gaps and uncertainty
Explain what is missing, weakly supported, or requires further research.

## 6. References
List all used sources in this format:
[Source ID] Title - URL

## 7. Follow-up research questions
List 3 useful follow-up search questions.
"""

    time_range_description = describe_time_range(time_range)

    prompt = f"""
You are a professional Web Search Agent V2. You specialize in integrating bilingual, multi-source search results into structured research reports.

Original user query:
{query}

English search query generated from the original query:
{english_query}

Detected time range:
{time_range_description}

Search materials from Tavily, Google, NewsAPI and other sources:
{context}

{language_instruction}

Rules:
1. Do not make up information that is not supported by the search materials.
2. Important conclusions must include source citations such as [1], [2], or [1][3].
3. If multiple sources support the same conclusion, cite multiple sources.
4. If sources conflict, point this out clearly.
5. Keep the report structured and suitable for copying into a document.
6. Use the same source IDs provided in the search materials.
7. If a detected time range is provided, only use materials that match that time range and mention the time range in the report.
8. Do not use older background knowledge as evidence for time-sensitive claims.

Report format:

{title}

{section_names}
"""

    response = client.chat.completions.create(
        model=os.getenv("OFOX_MODEL"),
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    return response.choices[0].message.content


def summarize_search(query: str):
    """
    Agent 主函数

    工作流程：
    1. 将用户输入自动翻译成英文搜索关键词
    2. 使用中文 Query 搜索
    3. 使用英文 Query 搜索
    4. 融合、去重并重新编号来源
    5. 基于同一批资料生成中文报告和英文报告
    6. 返回双语报告，供前端一键切换显示
    """

    # -------------------------
    # 第一步：识别用户是否提出相对时间范围
    # -------------------------
    time_range = detect_time_range(query)

    # -------------------------
    # 第二步：自动翻译英文搜索关键词
    # -------------------------
    english_query = translate_query_to_english(query)

    # -------------------------
    # 第三步：中文搜索 + 英文搜索
    # -------------------------
    cn_results = multi_source_search(
        query,
        max_results_per_source=5,
        language="zh",
        time_range=time_range
    )

    en_results = multi_source_search(
        english_query,
        max_results_per_source=5,
        language="en",
        time_range=time_range
    )

    # -------------------------
    # 第三步：结果融合、去重、重新编号
    # -------------------------
    results = cn_results + en_results
    results = deduplicate_results(results)
    results = add_source_ids(results)

    if not results:
        return {
            "chinese": "没有搜索到可用结果，请检查 API Key 配置或更换搜索关键词。",
            "english": "No usable search results were found. Please check your API key configuration or try another query.",
            "english_query": english_query,
            "time_range": time_range.to_dict() if time_range else None,
            "sources": []
        }

    # -------------------------
    # 第四步：构造上下文
    # -------------------------
    context = build_context(results)

    # -------------------------
    # 第五步：生成中文报告 + 英文报告
    # -------------------------
    chinese_report = generate_report(
        query=query,
        english_query=english_query,
        context=context,
        report_language="zh",
        time_range=time_range
    )

    english_report = generate_report(
        query=query,
        english_query=english_query,
        context=context,
        report_language="en",
        time_range=time_range
    )

    # -------------------------
    # 第六步：返回结构化结果
    # -------------------------
    return {
        "chinese": chinese_report,
        "english": english_report,
        "english_query": english_query,
        "time_range": time_range.to_dict() if time_range else None,
        "sources": results
    }
