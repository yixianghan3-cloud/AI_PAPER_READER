# ============================================================
# 【1号位】app.py - 主入口 (v4 终版 · 模块化)
# ============================================================
# 模块边界:
#   app.py                     ← 本文件: 状态管理 / Pipeline 编排 / 侧栏 / 主路由
#   components/styles.py       ← 所有 CSS
#   components/views.py        ← 三个 view 渲染函数 + mindmap/pdf 辅助
#   contracts/                 ← 2/3/4 号位的接口契约
# ============================================================
# 运行方式:
#   streamlit run app.py
# 依赖:
#   pip install streamlit streamlit-echarts
#   Streamlit 1.39+（需要 st.segmented_control）
# ============================================================

import os
import sys
import time
import traceback

import streamlit as st

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts.search_contract import search_papers
from contracts.parse_contract import parse_pdf
from contracts.llm_contract import summarize_paper

from components.styles import inject_styles
from components.views import (
    render_landing,
    render_single_view,
    render_pdf_compare_view,
)


# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="论文摘要助手",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Session State
# ============================================================
def init_state():
    defaults = {
        "query"         : "",
        "papers"        : [],
        "parsed_list"   : [],
        "summaries"     : [],
        "errors"        : [],
        "timings"       : {},
        "selected_idx"  : 0,
        "view_mode"     : "single",       # single | pdf_compare
        "run_pipeline"  : False,
        "max_results"   : 3,
        "lang"          : "zh",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
inject_styles()


# ============================================================
# 兜底解析 / 摘要
# ============================================================
def safe_parse(paper):
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


def safe_summarize(parsed, lang):
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
# Pipeline 执行
# ============================================================
def run_pipeline_now(query: str, max_results: int, lang: str):
    st.session_state.query        = query
    st.session_state.papers       = []
    st.session_state.parsed_list  = []
    st.session_state.summaries    = []
    st.session_state.errors       = []
    st.session_state.timings      = {}
    st.session_state.selected_idx = 0
    st.session_state.view_mode    = "single"

    with st.status("Pipeline 运行中...", expanded=True) as status:
        try:
            st.write("**[1/3] 检索论文**")
            t0 = time.time()
            papers = search_papers(query, max_results=max_results)
            st.session_state.papers = papers
            st.session_state.timings["search"] = time.time() - t0
            if not papers:
                status.update(label="未检索到论文", state="error")
                st.stop()
            st.write(f"  └ 找到 {len(papers)} 篇  ({st.session_state.timings['search']:.1f}s)")

            st.write("**[2/3] 解析 PDF**")
            t0 = time.time()
            parse_bar = st.progress(0.0, text="准备解析...")
            parsed_list = []
            for i, p in enumerate(papers):
                parse_bar.progress(i / len(papers),
                                   text=f"解析中 {i + 1}/{len(papers)}: {p['title'][:50]}")
                parsed_list.append(safe_parse(p))
            parse_bar.progress(1.0, text="解析完成")
            st.session_state.parsed_list = parsed_list
            st.session_state.timings["parse"] = time.time() - t0
            ok = sum(1 for x in parsed_list if x)
            st.write(f"  └ 解析成功 {ok}/{len(papers)}  ({st.session_state.timings['parse']:.1f}s)")

            st.write("**[3/3] 生成摘要**")
            t0 = time.time()
            sum_bar = st.progress(0.0, text="准备摘要...")
            summaries = []
            for i, parsed in enumerate(parsed_list):
                title = (parsed or {}).get("title", papers[i]["title"])
                sum_bar.progress(i / len(parsed_list),
                                 text=f"摘要中 {i + 1}/{len(parsed_list)}: {title[:50]}")
                summaries.append(safe_summarize(parsed, lang))
            sum_bar.progress(1.0, text="摘要完成")
            st.session_state.summaries = summaries
            st.session_state.timings["summarize"] = time.time() - t0
            ok = sum(1 for x in summaries if x)
            st.write(f"  └ 摘要成功 {ok}/{len(parsed_list)}  ({st.session_state.timings['summarize']:.1f}s)")

            status.update(label="全部完成", state="complete", expanded=False)
        except Exception as e:
            status.update(label=f"Pipeline 异常: {e}", state="error")
            st.exception(e)
            st.code(traceback.format_exc())


# ============================================================
# 侧栏: 设置（含署名） + 论文列表 + 新搜索 + 调试
# ============================================================
with st.sidebar:
    with st.expander("设置", expanded=False):
        st.session_state.max_results = st.slider(
            "检索论文数量", 1, 10, st.session_state.max_results
        )
        st.session_state.lang = st.radio(
            "摘要语言", ["zh", "en"], horizontal=True,
            index=0 if st.session_state.lang == "zh" else 1,
        )
        st.divider()
        st.caption("关于")
        st.caption("1–5 号位 · 某某课程 · 2026")

    st.divider()

    # 已有结果时: 显示论文列表 + 新搜索入口
    if st.session_state.papers:
        ok_count = sum(1 for x in st.session_state.summaries if x)
        total_t = sum(st.session_state.timings.values())
        st.markdown(
            '<p class="grad-text" style="font-size:16px; margin:0 0 2px;">论文列表</p>',
            unsafe_allow_html=True,
        )
        st.caption(f"{len(st.session_state.papers)} 篇 · 摘要成功 {ok_count} · {total_t:.1f}s")

        for i, paper in enumerate(st.session_state.papers):
            is_sel = (st.session_state.selected_idx == i)
            summ_ok = (
                i < len(st.session_state.summaries)
                and st.session_state.summaries[i] is not None
            )
            authors_list = paper.get("authors") or []
            authors_disp = (
                (authors_list[0] if authors_list else "?")
                + (" et al." if len(authors_list) > 1 else "")
            )
            badge = (
                '<span class="sb-badge">已生成</span>'
                if summ_ok
                else '<span class="sb-badge sb-badge-warn">失败</span>'
            )
            st.markdown(f"""
<div class="sb-card {'sb-card-sel' if is_sel else ''}">
  <div class="sb-title">{paper['title']}</div>
  <div class="sb-meta">{authors_disp} · {paper.get('year', '?')} · {paper.get('source', '?')}</div>
  {badge}
</div>
""", unsafe_allow_html=True)

            if not is_sel:
                if st.button("查看 →", key=f"sel_btn_{i}", use_container_width=True):
                    st.session_state.selected_idx = i
                    st.rerun()
            else:
                st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

        st.divider()

        with st.expander("新搜索", expanded=False):
            new_q = st.text_input(
                "关键词",
                placeholder="例如: diffusion models",
                label_visibility="collapsed",
                key="new_search_input",
            )
            if st.button("重新搜索", use_container_width=True, type="primary") and new_q.strip():
                st.session_state.query = new_q
                st.session_state.run_pipeline = True
                st.rerun()

    else:
        st.caption("（运行搜索后，论文列表会出现在这里）")

    st.divider()

    with st.expander("调试"):
        if st.button("清空所有状态", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.json({
            "papers_count"  : len(st.session_state.papers),
            "parsed_count"  : sum(1 for x in st.session_state.parsed_list if x),
            "summary_count" : sum(1 for x in st.session_state.summaries if x),
            "errors_count"  : len(st.session_state.errors),
            "selected_idx"  : st.session_state.selected_idx,
            "view_mode"     : st.session_state.view_mode,
            "timings"       : st.session_state.timings,
        })


# ============================================================
# 主流程
# ============================================================

# Pipeline 触发器（起始页 / 侧栏新搜索 / chip 任一处设置 run_pipeline=True）
if st.session_state.run_pipeline:
    st.session_state.run_pipeline = False
    run_pipeline_now(
        st.session_state.query,
        st.session_state.max_results,
        st.session_state.lang,
    )
    st.rerun()


# 主区域路由: 无结果 → 起始页；有结果 → 详情视图（带模式切换）
if not st.session_state.summaries:
    render_landing()
else:
    # 顶部主标题
    st.markdown('<div class="app-title">论文摘要助手</div>', unsafe_allow_html=True)

    # 全局指标
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("检索篇数", len(st.session_state.papers))
    m2.metric("解析成功", sum(1 for x in st.session_state.parsed_list if x))
    m3.metric("摘要成功", sum(1 for x in st.session_state.summaries if x))
    m4.metric("总耗时", f"{sum(st.session_state.timings.values()):.1f}s")

    if st.session_state.errors:
        with st.expander(f"{len(st.session_state.errors)} 条错误信息"):
            for e in st.session_state.errors:
                st.error(e)

    st.divider()

    # 视图模式切换 pills
    mode_label = st.segmented_control(
        "视图模式",
        options=["单视图", "PDF + 摘要"],
        default="单视图" if st.session_state.view_mode == "single" else "PDF + 摘要",
        label_visibility="collapsed",
        key="view_mode_pills",
    )
    new_mode = "single" if mode_label == "单视图" else "pdf_compare"
    if new_mode != st.session_state.view_mode:
        st.session_state.view_mode = new_mode
        st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # 渲染选中那一篇
    idx = st.session_state.selected_idx
    if 0 <= idx < len(st.session_state.papers):
        paper  = st.session_state.papers[idx]
        parsed = st.session_state.parsed_list[idx]
        summ   = st.session_state.summaries[idx]

        if st.session_state.view_mode == "single":
            render_single_view(paper, parsed, summ)
        else:
            render_pdf_compare_view(paper, parsed, summ)