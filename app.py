# ============================================================
# 【1号位】app.py - 主入口
# 基于 contracts/ 下三份接口契约串联整条 Pipeline
# 运行方式：streamlit run app.py
# ============================================================

import os
import sys
import time
import traceback

import streamlit as st
import streamlit.components.v1 as components

# 将项目根目录加入 path，确保能 import contracts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts.search_contract import search_papers
from contracts.parse_contract import parse_pdf
from contracts.llm_contract import summarize_paper


# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="学术论文智能摘要系统",
    page_icon="📚",
    layout="wide",
)


# ============================================================
# Session State 初始化
# 注意：Streamlit 每次交互都会重跑整个脚本，所有跨步骤数据
#       必须存进 session_state，不能用普通变量
# ============================================================
def init_state():
    defaults = {
        "stage"       : "input",   # input / running / done
        "query"       : "",
        "papers"      : [],        # search_papers 返回
        "parsed_list" : [],        # 每篇 parse_pdf 的返回（失败为 None）
        "summaries"   : [],        # 每篇 summarize_paper 的返回（失败为 None）
        "errors"      : [],
        "timings"     : {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ============================================================
# 思维导图渲染（Markmap CDN）
# ============================================================
def render_mindmap(markdown_text: str, height: int = 500):
    """用 Markmap 把 markdown 渲染成可交互思维导图。"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ margin: 0; padding: 0; }}
        .markmap {{ width: 100%; height: {height}px; }}
      </style>
      <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.16"></script>
    </head>
    <body>
      <div class="markmap">
        <script type="text/template">
{markdown_text}
        </script>
      </div>
    </body>
    </html>
    """
    components.html(html, height=height + 20)


# ============================================================
# 单篇论文兜底解析（Mock 阶段 local_path 为空时使用）
# ============================================================
def safe_parse(paper: dict) -> dict | None:
    """
    包一层 try/except，单篇失败不影响其他论文。
    Mock 阶段 local_path 为空时，退化为用 abstract 当正文。
    """
    try:
        local_path = paper.get("local_path", "")
        if not local_path:
            abstract = paper.get("abstract", "")
            return {
                "title"        : paper.get("title", ""),
                "full_text"    : abstract,
                "sections"     : [{"title": "Abstract", "content": abstract}],
                "word_count"   : len(abstract.split()),
                "parse_method" : "fallback-abstract",
            }
        return parse_pdf(local_path)
    except Exception as e:
        st.session_state.errors.append(
            f"解析失败 - {paper.get('title', '?')[:40]}: {e}"
        )
        return None


def safe_summarize(parsed: dict | None, lang: str) -> dict | None:
    """单篇摘要失败不中断整个 pipeline。"""
    if parsed is None:
        return None
    try:
        return summarize_paper(parsed, lang=lang)
    except Exception as e:
        st.session_state.errors.append(
            f"摘要失败 - {parsed.get('title', '?')[:40]}: {e}"
        )
        return None


# ============================================================
# Sidebar 配置区
# ============================================================
with st.sidebar:
    st.title("⚙️ 设置")
    max_results = st.slider("检索论文数量", 1, 10, 3)
    lang = st.radio("摘要语言", ["zh", "en"], horizontal=True, index=0)

    st.divider()
    st.caption("调试")
    if st.button("🔄 清空所有状态", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    with st.expander("当前状态快照"):
        st.json({
            "papers_count"   : len(st.session_state.papers),
            "parsed_count"   : sum(1 for x in st.session_state.parsed_list if x),
            "summary_count"  : sum(1 for x in st.session_state.summaries if x),
            "errors_count"   : len(st.session_state.errors),
            "timings"        : st.session_state.timings,
        })


# ============================================================
# 主标题
# ============================================================
st.title("📚 学术论文智能摘要系统")
st.caption("关键词 → 检索 → PDF 解析 → 大模型摘要 → 思维导图")


# ============================================================
# 步骤 1：输入关键词
# ============================================================
query = st.text_input(
    "研究关键词",
    value=st.session_state.query,
    placeholder="例如：transformer attention mechanism",
)

col_run, col_demo, _ = st.columns([1, 1, 4])
run = col_run.button("🚀 开始处理", type="primary", disabled=not query.strip())
demo = col_demo.button("🎲 用 Demo 示例")

if demo:
    query = "attention is all you need"
    run = True
    st.session_state.query = query


# ============================================================
# Pipeline 执行
# ============================================================
if run:
    # 清空上次结果
    st.session_state.query       = query
    st.session_state.papers      = []
    st.session_state.parsed_list = []
    st.session_state.summaries   = []
    st.session_state.errors      = []
    st.session_state.timings     = {}

    with st.status("Pipeline 运行中...", expanded=True) as status:
        try:
            # ---------- Step 1: 搜索 ----------
            st.write("🔍 **[1/3] 检索论文...**")
            t0 = time.time()
            papers = search_papers(query, max_results=max_results)
            st.session_state.papers = papers
            st.session_state.timings["search"] = time.time() - t0

            if not papers:
                status.update(label="❌ 未检索到论文", state="error")
                st.stop()

            st.write(
                f"   ✓ 找到 {len(papers)} 篇  "
                f"(耗时 {st.session_state.timings['search']:.1f}s)"
            )

            # ---------- Step 2: 解析 ----------
            st.write("📄 **[2/3] 解析 PDF...**")
            t0 = time.time()
            parse_bar = st.progress(0.0, text="准备解析...")
            parsed_list = []
            for i, p in enumerate(papers):
                parse_bar.progress(
                    i / len(papers),
                    text=f"解析中 {i + 1}/{len(papers)}：{p['title'][:50]}",
                )
                parsed_list.append(safe_parse(p))
            parse_bar.progress(1.0, text="解析完成")

            st.session_state.parsed_list = parsed_list
            st.session_state.timings["parse"] = time.time() - t0
            ok = sum(1 for x in parsed_list if x)
            st.write(
                f"   ✓ 解析成功 {ok}/{len(papers)}  "
                f"(耗时 {st.session_state.timings['parse']:.1f}s)"
            )

            # ---------- Step 3: 摘要 ----------
            st.write("🤖 **[3/3] 生成摘要...**")
            t0 = time.time()
            sum_bar = st.progress(0.0, text="准备摘要...")
            summaries = []
            for i, parsed in enumerate(parsed_list):
                title = (parsed or {}).get("title", papers[i]["title"])
                sum_bar.progress(
                    i / len(parsed_list),
                    text=f"摘要中 {i + 1}/{len(parsed_list)}：{title[:50]}",
                )
                summaries.append(safe_summarize(parsed, lang))
            sum_bar.progress(1.0, text="摘要完成")

            st.session_state.summaries = summaries
            st.session_state.timings["summarize"] = time.time() - t0
            ok = sum(1 for x in summaries if x)
            st.write(
                f"   ✓ 摘要成功 {ok}/{len(parsed_list)}  "
                f"(耗时 {st.session_state.timings['summarize']:.1f}s)"
            )

            status.update(label="✅ 全部完成", state="complete", expanded=False)

        except Exception as e:
            status.update(label=f"❌ Pipeline 异常：{e}", state="error")
            st.exception(e)
            st.code(traceback.format_exc())


# ============================================================
# 结果展示
# ============================================================
if st.session_state.summaries:
    st.divider()

    # ---- 总览指标 ----
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("检索篇数", len(st.session_state.papers))
    m2.metric("解析成功", sum(1 for x in st.session_state.parsed_list if x))
    m3.metric("摘要成功", sum(1 for x in st.session_state.summaries if x))
    m4.metric("总耗时", f"{sum(st.session_state.timings.values()):.1f}s")

    # ---- 错误信息 ----
    if st.session_state.errors:
        with st.expander(f"⚠️ {len(st.session_state.errors)} 条错误信息"):
            for e in st.session_state.errors:
                st.error(e)

    # ---- 每篇论文详情 ----
    st.subheader("📋 论文摘要结果")

    iterator = zip(
        st.session_state.papers,
        st.session_state.parsed_list,
        st.session_state.summaries,
    )
    for i, (paper, parsed, summ) in enumerate(iterator):
        with st.expander(
            f"**[{i + 1}] {paper['title']}**",
            expanded=(i == 0),
        ):
            # 元信息行
            meta_l, meta_r = st.columns([2, 1])
            with meta_l:
                authors = ", ".join(paper.get("authors", []))
                year = paper.get("year") or "未知"
                source = paper.get("source", "-")
                st.markdown(f"**作者**：{authors or '未知'}")
                st.markdown(f"**年份**：{year}　|　**来源**：`{source}`")
                if paper.get("pdf_url"):
                    st.markdown(f"[📥 PDF 原始链接]({paper['pdf_url']})")
            with meta_r:
                if parsed:
                    st.metric("字数", parsed.get("word_count", 0))
                    st.caption(
                        f"解析方式：`{parsed.get('parse_method', '-')}`"
                    )

            if summ is None:
                st.warning("此论文摘要生成失败，请查看错误信息")
                continue

            # Tab 切换
            tab1, tab2, tab3, tab4 = st.tabs(
                ["📝 摘要", "🧠 思维导图", "🔑 关键词", "📄 原文章节"]
            )

            with tab1:
                st.markdown("### 一句话总结")
                st.info(summ["one_sentence"])

                st.markdown("### 结构化总结")
                ss = summ["structured_summary"]
                st.markdown(f"**🎯 研究问题**　{ss['problem']}")
                st.markdown(f"**🔧 方法**　{ss['method']}")
                st.markdown(f"**📊 结果**　{ss['result']}")
                st.markdown(f"**⭐ 贡献**　{ss['contribution']}")
                st.caption(f"使用模型：`{summ.get('model_used', '-')}`")

            with tab2:
                render_mindmap(summ["mindmap_markdown"], height=500)
                with st.popover("查看 Markdown 源码"):
                    st.code(summ["mindmap_markdown"], language="markdown")

            with tab3:
                kws = summ.get("keywords", [])
                if kws:
                    cols = st.columns(len(kws))
                    for j, kw in enumerate(kws):
                        cols[j].markdown(f"### `{kw}`")
                else:
                    st.caption("无关键词")

            with tab4:
                if parsed:
                    for sec in parsed.get("sections", []):
                        st.markdown(f"#### {sec['title']}")
                        st.markdown(sec["content"] or "_(空)_")
                else:
                    st.warning("解析失败，无原文可显示")

else:
    if not run:
        st.info("👆 输入关键词后点击「开始处理」，或点「Demo 示例」快速体验")