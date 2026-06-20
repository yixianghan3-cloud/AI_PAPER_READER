# ============================================================
# components/styles.py
# ============================================================
# 所有 v4 渐变 / 深色 / 布局相关的 CSS 集中在这里
# 主流程不关心样式细节，改 UI 只需要看这一份文件
# ============================================================

import streamlit as st


def inject_styles():
    """v4 渐变 + 深色主题的全部 CSS。在 app.py 顶部调用一次。"""
    st.markdown("""
    <style>
      /* —— 设计令牌（蓝紫红主题，改色只动这一处）—————————————— */
      :root {
        --c1: #4285F4;            /* 蓝 */
        --c2: #9B72CB;            /* 紫 */
        --c3: #D96570;            /* 红 */
        --grad: linear-gradient(135deg, var(--c1) 0%, var(--c2) 50%, var(--c3) 100%);
        --grad-2: linear-gradient(135deg, var(--c1), var(--c2));

        --surface: #1A1C20;       /* 卡片底 */
        --surface-hi: #202329;    /* 卡片 hover 底 */
        --border: #2A2C32;        /* 描边 */
        --text: #F0F1F4;          /* 正文 */
        --dim: #A6ADBA;           /* 次要文字（由 #9CA3AF 提亮，过对比度 4.5:1）*/
        --dim-2: #C8CDD5;         /* chip 文字 */
        --ring: rgba(155,114,203,0.55);  /* 焦点环 */
      }

      /* —— 全局过渡 & 焦点可见（可访问性）———————————————— */
      .grid-cell, .chip, .sb-card,
      section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        transition: background .18s ease, border-color .18s ease, transform .18s ease;
      }
      :focus-visible {
        outline: 2px solid var(--ring);
        outline-offset: 2px;
        border-radius: 6px;
      }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { transition: none !important; animation: none !important; }
      }

      /* —— Gemini 极简起始页 —— */
      .hero-title {
        font-size: 48px;
        font-weight: 500;
        text-align: center;
        margin: 0 0 10px;
        background: var(--grad);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
        line-height: 1.15;
      }
      .hero-sub {
        font-size: 15px;
        color: var(--dim);
        margin: 0 0 38px;
        text-align: center;
        letter-spacing: 0.02em;
      }

      /* —— 详情页主标题（结果区） —— */
      .app-title {
        font-size: 34px;
        font-weight: 500;
        margin: 0 0 4px;
        background: var(--grad);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.02em;
        line-height: 1.2;
      }
      .app-sub {
        color: var(--dim);
        font-size: 13px;
        margin: 0 0 14px;
      }

      /* —— 渐变文字工具类 —— */
      .grad-text {
        background: var(--grad-2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 600;
      }

      /* —— AI 渐变锚点条 —— */
      .ai-strip {
        height: 3px;
        border-radius: 999px;
        margin: 8px 0 14px;
        background: var(--grad);
      }

      /* —— 一句话总结 callout（深色 22% 浓度） —— */
      .summary-callout {
        background: linear-gradient(135deg,
                    rgba(66,133,244,0.22) 0%,
                    rgba(155,114,203,0.17) 55%,
                    rgba(217,101,112,0.10) 100%);
        border: 0.5px solid rgba(155,114,203,0.35);
        border-radius: 8px;
        padding: 14px 16px;
        margin: 6px 0 20px;
        font-size: 15px;
        line-height: 1.7;
        color: var(--text);
      }

      /* —— 结构化总结 2x2 网格 —— */
      .grid-2x2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin: 6px 0 16px;
      }
      .grid-cell {
        background: var(--surface);
        border: 0.5px solid var(--border);
        border-radius: 8px;
        padding: 13px 15px;
      }
      .grid-cell:hover {
        background: var(--surface-hi);
        border-color: rgba(155,114,203,0.40);
      }
      .cell-label {
        font-size: 12.5px;
        font-weight: 600;
        letter-spacing: 0.3px;
        margin-bottom: 5px;
        background: var(--grad-2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
      .cell-text {
        font-size: 14px;
        color: var(--text);
        line-height: 1.6;
      }

      /* —— 关键词 chips —— */
      .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
      .chip {
        background: var(--surface);
        border: 0.5px solid var(--border);
        border-radius: 999px;
        padding: 5px 13px;
        font-size: 13px;
        color: var(--dim-2);
      }
      .chip:hover {
        background: var(--surface-hi);
        border-color: rgba(155,114,203,0.45);
        color: var(--text);
      }

      /* —— 侧栏论文卡片 —— */
      .sb-card {
        background: var(--surface);
        border: 0.5px solid var(--border);
        border-radius: 8px;
        padding: 10px 12px;
        margin: 4px 0 2px;
      }
      .sb-card:hover {
        background: var(--surface-hi);
        border-color: rgba(155,114,203,0.40);
      }
      .sb-card-sel {
        background: linear-gradient(135deg,
                    rgba(66,133,244,0.18) 0%,
                    rgba(155,114,203,0.13) 55%,
                    rgba(217,101,112,0.08) 100%);
        border: 0.5px solid rgba(66,133,244,0.55);
      }
      .sb-title {
        font-size: 13px;
        font-weight: 500;
        color: var(--text);
        line-height: 1.45;
        margin-bottom: 4px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .sb-meta {
        font-size: 12px;
        color: var(--dim);
        margin-bottom: 4px;
      }
      .sb-badge {
        display: inline-block;
        font-size: 11px;
        padding: 1px 8px;
        border-radius: 999px;
        background: rgba(66,133,244,0.18);
        color: #A8C7FA;
      }
      .sb-badge-warn {
        background: rgba(234,67,53,0.18);
        color: #F2B8B5;
      }

      /* —— 让 sidebar 按钮更紧凑 —— */
      section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        font-size: 13px;
        padding: 4px 12px;
        min-height: 30px;
      }

      /* —— PDF 对比模式：对照阅读提示条 —— */
      .verify-strip {
        background: linear-gradient(135deg, rgba(66,133,244,0.10), rgba(155,114,203,0.08));
        border: 0.5px dashed rgba(155,114,203,0.40);
        border-radius: 8px;
        padding: 9px 12px;
        font-size: 12px;
        color: var(--dim);
        margin: 0 0 12px;
        line-height: 1.55;
      }
      .verify-strip strong {
        background: var(--grad-2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      /* —— PDF 模式收起侧栏提示 —— */
      .hint-pill {
        background: rgba(155,114,203,0.10);
        border: 0.5px solid rgba(155,114,203,0.25);
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        color: #C8B6E2;
        margin: 0 0 14px;
      }
    </style>
    """, unsafe_allow_html=True)