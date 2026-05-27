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
      /* —— Gemini 极简起始页 —— */
      .hero-title {
        font-size: 48px;
        font-weight: 500;
        text-align: center;
        margin: 0 0 10px;
        background: linear-gradient(135deg, #4285F4 0%, #9B72CB 50%, #D96570 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
        line-height: 1.15;
      }
      .hero-sub {
        font-size: 14px;
        color: #9CA3AF;
        margin: 0 0 38px;
        text-align: center;
        letter-spacing: 0.02em;
      }

      /* —— 详情页主标题（结果区） —— */
      .app-title {
        font-size: 34px;
        font-weight: 500;
        margin: 0 0 4px;
        background: linear-gradient(90deg, #4285F4 0%, #9B72CB 50%, #D96570 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.02em;
        line-height: 1.2;
      }
      .app-sub {
        color: #9CA3AF;
        font-size: 13px;
        margin: 0 0 14px;
      }

      /* —— 渐变文字工具类 —— */
      .grad-text {
        background: linear-gradient(135deg, #4285F4, #9B72CB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 500;
      }

      /* —— AI 渐变锚点条 —— */
      .ai-strip {
        height: 3px;
        border-radius: 999px;
        margin: 8px 0 14px;
        background: linear-gradient(90deg, #4285F4, #9B72CB, #D96570);
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
        font-size: 14px;
        line-height: 1.65;
        color: #F0F1F4;
      }

      /* —— 结构化总结 2x2 网格 —— */
      .grid-2x2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin: 6px 0 16px;
      }
      .grid-cell {
        background: #1A1C20;
        border: 0.5px solid #2A2C32;
        border-radius: 8px;
        padding: 12px 14px;
      }
      .cell-label {
        font-size: 12px;
        font-weight: 500;
        letter-spacing: 0.3px;
        margin-bottom: 4px;
        background: linear-gradient(135deg, #4285F4, #9B72CB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
      .cell-text {
        font-size: 13px;
        color: #F0F1F4;
        line-height: 1.55;
      }

      /* —— 关键词 chips —— */
      .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
      .chip {
        background: #1A1C20;
        border: 0.5px solid #2A2C32;
        border-radius: 999px;
        padding: 5px 12px;
        font-size: 12px;
        color: #C8CDD5;
      }

      /* —— 侧栏论文卡片 —— */
      .sb-card {
        background: #1A1C20;
        border: 0.5px solid #2A2C32;
        border-radius: 8px;
        padding: 10px 12px;
        margin: 4px 0 2px;
      }
      .sb-card-sel {
        background: linear-gradient(135deg,
                    rgba(66,133,244,0.18) 0%,
                    rgba(155,114,203,0.13) 55%,
                    rgba(217,101,112,0.08) 100%);
        border: 0.5px solid rgba(66,133,244,0.55);
      }
      .sb-title {
        font-size: 12px;
        font-weight: 500;
        color: #F0F1F4;
        line-height: 1.4;
        margin-bottom: 4px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .sb-meta {
        font-size: 11px;
        color: #9CA3AF;
        margin-bottom: 4px;
      }
      .sb-badge {
        display: inline-block;
        font-size: 10px;
        padding: 1px 7px;
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
        font-size: 12px;
        padding: 3px 12px;
        min-height: 28px;
      }

      /* —— PDF 对比模式：对照阅读提示条 —— */
      .verify-strip {
        background: linear-gradient(135deg, rgba(66,133,244,0.10), rgba(155,114,203,0.08));
        border: 0.5px dashed rgba(155,114,203,0.40);
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 11px;
        color: #9CA3AF;
        margin: 0 0 12px;
        line-height: 1.5;
      }
      .verify-strip strong {
        background: linear-gradient(135deg, #4285F4, #9B72CB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      /* —— PDF 模式收起侧栏提示 —— */
      .hint-pill {
        background: rgba(155,114,203,0.10);
        border: 0.5px solid rgba(155,114,203,0.25);
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 12px;
        color: #C8B6E2;
        margin: 0 0 14px;
      }
    </style>
    """, unsafe_allow_html=True)