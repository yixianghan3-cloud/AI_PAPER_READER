# ============================================================
# components/views.py
# ============================================================
# 三个主 view 函数:
#   - render_landing()           : Gemini 极简起始页
#   - render_single_view()       : 单视图详情（4 个 tab）
#   - render_pdf_compare_view()  : PDF + 摘要 对比视图
#
# 以及两个内部渲染辅助:
#   - render_mindmap_echarts()   : 思维导图（ECharts tree）
#   - render_pdf_iframe()        : PDF 嵌入（带 URL fragment 高亮）
#
# 注意: 这里只负责 UI 渲染，不持有任何业务状态
# ============================================================

from urllib.parse import quote

import streamlit as st
from streamlit_echarts import st_echarts


# ============================================================
# 全文来源推断（显示层，不改契约 source 字段）
# ============================================================
# source 字段是「检索引擎」(openalex/arxiv...)，永远一个值、信息量低。
# 这里从 pdf_url 推断「全文实际来源」(arXiv / 出版商 / 仅摘要)，更有用。
_PUBLISHER_HOSTS = {
    "arxiv.org":      "arXiv",
    "aaai.org":       "AAAI",
    "ieee":           "IEEE",
    "acm.org":        "ACM",
    "openreview":     "OpenReview",
    "mlr.press":      "PMLR",
    "neurips":        "NeurIPS",
    "springer":       "Springer",
    "sciencedirect":  "Elsevier",
    "nature.com":     "Nature",
    "biorxiv":        "bioRxiv",
    "hal.":           "HAL",
    "ssrn":           "SSRN",
}


def fulltext_source(paper: dict, parsed: dict = None) -> str:
    """返回「全文来源」短标签：arXiv / AAAI / … / 仅摘要。"""
    # 解析降级为摘要 → 明确标「仅摘要」
    if parsed and parsed.get("parse_method") == "fallback-abstract":
        return "仅摘要"
    url = (paper.get("pdf_url") or "").lower()
    if not url:
        return "仅摘要"
    for key, name in _PUBLISHER_HOSTS.items():
        if key in url:
            return name
    # 兜底：取主域名词（如 example.com → example）
    try:
        host = url.split("//", 1)[-1].split("/", 1)[0].replace("www.", "")
        parts = host.split(".")
        return parts[-2] if len(parts) >= 2 else (host or "网页")
    except Exception:
        return "网页"


# ============================================================
# 可配置常量
# ============================================================
# 起始页示例 chips（用户首次进入时看到的"快速开始"选项）
# 各演示一种输入方式，引导用户用上新能力：
#   精确标题(自动少而精) / 中文自然语言(自动改写+探索) / 英文关键词
LANDING_SAMPLE_CHIPS = [
    "Attention Is All You Need",   # 精确论文标题 → 直接命中经典
    "大模型如何减少幻觉",            # 中文自然语言 → 自动改写成英文检索
    "diffusion models",            # 英文关键词
    "in-context learning",
]


# ============================================================
# 内部辅助: Markdown -> ECharts Tree 数据
# ============================================================
def markdown_to_tree(md: str) -> dict:
    lines = [l.rstrip() for l in md.strip().split("\n") if l.strip()]
    root = None
    stack = []
    for line in lines:
        if line.lstrip().startswith("#"):
            stripped = line.lstrip()
            level = len(stripped) - len(stripped.lstrip("#"))
            name = stripped.lstrip("#").strip() or " "
            node = {"name": name, "children": []}
        elif line.lstrip().startswith(("-", "*")):
            indent = len(line) - len(line.lstrip())
            level = 10 + indent
            name = line.lstrip().lstrip("-*").strip()
            node = {"name": name, "children": []}
        else:
            continue
        if root is None:
            root = node
            stack = [(level, node)]
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root = node
            stack = []
        stack.append((level, node))
    return root or {"name": "空", "children": []}


def render_mindmap_echarts(markdown_text: str, height: int = 550):
    """ECharts tree 渲染思维导图（深色版调色：紫色节点 + 淡紫连线）"""
    tree_data = markdown_to_tree(markdown_text)
    options = {
        "backgroundColor": "transparent",
        "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
        "series": [{
            "type": "tree",
            "data": [tree_data],
            "top": "5%", "left": "12%", "bottom": "5%", "right": "20%",
            "symbolSize": 9,
            "orient": "LR",
            "initialTreeDepth": -1,
            "itemStyle": {
                "color": "#9B72CB",
                "borderColor": "#C8B6E2",
                "borderWidth": 1.5,
            },
            "lineStyle": {
                "color": "#7C6BA0",
                "width": 1.2,
                "curveness": 0.5,
            },
            "label": {
                "position": "left",
                "verticalAlign": "middle",
                "align": "right",
                "fontSize": 14,
                "color": "#F0F1F4",
            },
            "leaves": {
                "label": {
                    "position": "right",
                    "verticalAlign": "middle",
                    "align": "left",
                    "color": "#F0F1F4",
                }
            },
            "emphasis": {"focus": "descendant"},
            "expandAndCollapse": True,
            "animationDuration": 550,
            "animationDurationUpdate": 750,
            "roam": True,
        }],
    }
    st_echarts(options, height=f"{height}px")


# ============================================================
# 内部辅助: PDF iframe（带 URL fragment 关键词高亮）
# ============================================================
def render_pdf_iframe(pdf_url: str, height: int = 720, highlight: str = None):
    """
    用 iframe 嵌入 PDF。
    如果传入 highlight，会在 URL 后追加 #search=<word>，
    Chrome 内嵌的 PDF viewer 加载时会自动高亮该词（黄色）。
    """
    if not pdf_url:
        st.info("这篇论文没有公开的 PDF 链接，摘要基于其官方摘要生成。可点上方「PDF 原始链接」到来源站查看全文。")
        return

    src = pdf_url
    if highlight:
        src = f"{pdf_url}#search={quote(highlight)}"

    st.markdown(
        f"""<iframe src="{src}" width="100%" height="{height}px"
        style="border:0.5px solid #2A2C32; border-radius:8px;
        background:#FFFFFF;"></iframe>
        <p style="font-size:11px; color:#9CA3AF; margin:6px 0 0;">
        如果 PDF 加载失败或被拦截，
        <a href="{pdf_url}" target="_blank" style="color:#C8B6E2; text-decoration:none;">在新标签打开 ↗</a>
        </p>""",
        unsafe_allow_html=True,
    )


# ============================================================
# 起始页（无搜索结果时显示）
# ============================================================
def render_landing():
    """Gemini 极简起始页：大渐变标题 + pill 搜索 + 示例 chips"""
    # 垂直留白（接近 Gemini 的垂直中线，可按屏幕高度微调这个 vh 值）
    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">论文摘要助手</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">AI 论文研究助手 · 检索 · 解析 · 摘要 · 思维导图</p>',
        unsafe_allow_html=True,
    )

    # 居中容器（用列做横向收窄）
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        # 搜索表单（Enter 可触发）
        with st.form("landing_search_form", clear_on_submit=False, border=False):
            in_l, in_r = st.columns([5, 1])
            with in_l:
                q = st.text_input(
                    "搜索",
                    placeholder="想了解什么？关键词、中文描述、或论文标题都行",
                    label_visibility="collapsed",
                )
            with in_r:
                submit = st.form_submit_button(
                    "开始 →", type="primary", use_container_width=True
                )
            if submit and q.strip():
                st.session_state.query = q
                st.session_state.run_pipeline = True
                st.rerun()

        st.markdown('<div style="height: 14px;"></div>', unsafe_allow_html=True)

        # 示例 chips（列表定义在文件顶部 LANDING_SAMPLE_CHIPS）
        chip_cols = st.columns(len(LANDING_SAMPLE_CHIPS))
        for i, c in enumerate(LANDING_SAMPLE_CHIPS):
            if chip_cols[i].button(c, key=f"chip_{i}", use_container_width=True):
                st.session_state.query = c
                st.session_state.run_pipeline = True
                st.rerun()


# ============================================================
# 单视图详情（mindmap + 4 tabs）
# ============================================================
def render_single_view(paper, parsed, summ):
    """完整详情视图：标题、元信息、4 个 tab（摘要/思维导图/关键词/原始 PDF）"""
    st.markdown(f"### {paper['title']}")

    meta_l, meta_r = st.columns([2, 1])
    with meta_l:
        authors = ", ".join(paper.get("authors", []))
        year = paper.get("year") or "未知"
        engine = paper.get("source", "-")
        ft_src = fulltext_source(paper, parsed)
        st.markdown(f"**作者**: {authors or '未知'}")
        st.caption(f"**年份**: {year}　|　**全文来源**: `{ft_src}`　|　**检索自**: `{engine}`")
        if paper.get("pdf_url"):
            st.markdown(f"[PDF 原始链接 ↗]({paper['pdf_url']})")
    with meta_r:
        if parsed:
            st.metric("字数", parsed.get("word_count", 0))
            st.caption(f"解析方式: `{parsed.get('parse_method', '-')}`")

    if summ is None:
        st.warning("这篇论文没能生成摘要（多为 PDF 解析为空或内容过短）。"
                   "可在左侧换一篇试试，或重新检索更具体的关键词。")
        return

    st.markdown('<div class="ai-strip"></div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["摘要", "思维导图", "关键词", "原始 PDF"]
    )

    with tab1:
        st.markdown(
            '<p class="grad-text" style="font-size:14px; margin:0;">一句话总结</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="summary-callout">{summ["one_sentence"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="grad-text" style="font-size:14px; margin:0;">结构化总结</p>',
            unsafe_allow_html=True,
        )
        ss = summ["structured_summary"]
        st.markdown(f"""
<div class="grid-2x2">
  <div class="grid-cell">
    <div class="cell-label">研究问题</div>
    <div class="cell-text">{ss['problem']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">方法</div>
    <div class="cell-text">{ss['method']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">结果</div>
    <div class="cell-text">{ss['result']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">主要贡献</div>
    <div class="cell-text">{ss['contribution']}</div>
  </div>
</div>
""", unsafe_allow_html=True)
        st.caption(f"使用模型: `{summ.get('model_used', '-')}`")

    with tab2:
        render_mindmap_echarts(summ["mindmap_markdown"], height=550)
        st.caption("鼠标拖动平移视图，滚轮缩放，点击节点可折叠/展开")
        with st.popover("查看 Markdown 源码"):
            st.code(summ["mindmap_markdown"], language="markdown")

    with tab3:
        kws = summ.get("keywords", [])
        if kws:
            chips_html = "".join(f'<span class="chip">{kw}</span>' for kw in kws)
            st.markdown(f'<div class="chips">{chips_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("无关键词")

    with tab4:
        kws = summ.get("keywords", [])
        highlight = kws[0] if kws else None
        render_pdf_iframe(paper.get("pdf_url"), height=720, highlight=highlight)
        if highlight:
            st.caption(f"已自动高亮关键词：`{highlight}`（仅在 Chrome 内嵌 PDF viewer 生效）")


# ============================================================
# PDF + 摘要 对比视图
# ============================================================
def render_pdf_compare_view(paper, parsed, summ):
    """左右分屏：左侧 PDF 嵌入 + 右侧浓缩版摘要，强调对照阅读"""
    st.markdown(f"### {paper['title']}")
    st.caption(
        f"{', '.join(paper.get('authors', [])[:2])} · "
        f"{paper.get('year', '?')} · "
        f"全文来源 {fulltext_source(paper, parsed)}"
    )

    st.markdown(
        '<div class="hint-pill">建议点击左上 ☰ 收起侧栏，PDF 区域可获得更宽的阅读空间</div>',
        unsafe_allow_html=True,
    )

    if summ is None:
        st.warning("这篇论文没能生成摘要，暂时无法对照阅读。请在左侧换一篇，或重新检索。")
        return

    # 62/38 分屏
    pdf_col, sum_col = st.columns([62, 38])

    with pdf_col:
        kws = summ.get("keywords", [])
        highlight = kws[0] if kws else None
        render_pdf_iframe(paper.get("pdf_url"), height=720, highlight=highlight)

    with sum_col:
        st.markdown('<div class="ai-strip"></div>', unsafe_allow_html=True)

        verify_text = "摘要中的事实点可在左侧 PDF 中验证"
        if kws:
            verify_text = (
                f"已在左侧 PDF 中高亮关键词 <strong>{kws[0]}</strong>"
                "（仅 Chrome 生效）"
            )
        st.markdown(
            f'<div class="verify-strip"><strong>对照阅读模式</strong> · {verify_text}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="grad-text" style="font-size:13px; margin:0;">一句话总结</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="summary-callout">{summ["one_sentence"]}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="grad-text" style="font-size:13px; margin:0;">结构化总结</p>',
            unsafe_allow_html=True,
        )
        ss = summ["structured_summary"]
        st.markdown(f"""
<div class="grid-2x2">
  <div class="grid-cell">
    <div class="cell-label">问题</div>
    <div class="cell-text">{ss['problem']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">方法</div>
    <div class="cell-text">{ss['method']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">结果</div>
    <div class="cell-text">{ss['result']}</div>
  </div>
  <div class="grid-cell">
    <div class="cell-label">贡献</div>
    <div class="cell-text">{ss['contribution']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        st.markdown(
            '<p class="grad-text" style="font-size:13px; margin:0;">关键词</p>',
            unsafe_allow_html=True,
        )
        if kws:
            chips_html = "".join(f'<span class="chip">{kw}</span>' for kw in kws)
            st.markdown(f'<div class="chips">{chips_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("无关键词")

        st.caption("思维导图请切换至「单视图」模式查看")