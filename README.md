# web-search-agent

Web Search Agent V2.2 Stable 是一个基于 Streamlit 的双语网页搜索总结工具。它会识别用户问题中的时间范围，执行中英文多来源搜索，并生成可在中文和 English 之间切换的结构化研究报告。

## V2.2 功能

- Tavily 搜索
- Google Custom Search 支持
- NewsAPI 支持
- 中英文双语搜索
- 时间感知搜索，例如“今天”“最近”“本周”“本月”
- 来源统计，包括总来源数、搜索源分布、语言分布
- 双语报告切换
- 搜索源启用、跳过和失败状态展示

## 可选搜索源

Tavily、Google Search、NewsAPI 会按 `.env` 配置自动启用。

Google Search 和 NewsAPI 是可选配置：如果没有配置对应 API Key，程序不会崩溃，会在页面上显示已跳过搜索源和跳过原因。

## 环境变量示例

在项目根目录创建 `.env`：

```env
TAVILY_API_KEY=
OFOX_API_KEY=
OFOX_BASE_URL=
OFOX_MODEL=
GOOGLE_API_KEY=
GOOGLE_CSE_ID=
NEWS_API_KEY=
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

示例输入：

```text
今天 AI 领域发生了哪些重要新闻？
```

页面会显示英文搜索关键词、时间范围、已启用搜索源、已跳过搜索源、来源统计，以及中文 / English 报告切换。

## 测试

```bash
python -m py_compile app.py agent.py search_tool.py time_awareness.py
pytest
```
