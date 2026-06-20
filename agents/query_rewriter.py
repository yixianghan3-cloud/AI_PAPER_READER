# 负责人：2号位 / 4号位协作（检索前置 · 查询改写）
# 描述：把用户的自然语言诉求（可中文）改写成适合学术检索的英文关键词。
#       一举两得：① 提升召回与相关性；② 解决「中文搜不到英文库」。
# ============================================================
# 设计：复用 4号位 llm_agent 的 DeepSeek 封装；任何失败都「兜底返回原文」，
#       绝不因改写失败而阻断检索主流程。
# ============================================================
# -*- coding: utf-8 -*-

import re

# 复用 DeepSeek 封装（容错：llm_agent 不可用时降级为「原样返回」）
try:
    from agents.llm_agent import _call_deepseek
except Exception:
    _call_deepseek = None


# 系统提示词：身份 + 规则（与用户输入分离，指令更稳定，不易被正文带偏）
_SYSTEM = (
    "You are a query-rewriting assistant for academic paper databases "
    "(arXiv / OpenAlex). You turn a user's research interest into an English "
    "search query.\n"
    "Rules:\n"
    "- Output ONLY the search query: 2-6 English keywords/phrases, space-separated.\n"
    "- No explanation, no punctuation, no quotes, single line.\n"
    "- Translate non-English (e.g. Chinese) input into standard English domain terms.\n"
    "- If the input is ALREADY clean English keywords or an exact paper title, "
    "return it UNCHANGED (do not paraphrase, expand, or add synonyms). "
    "Preserving a precise title keeps retrieval accurate.\n"
    "- If the user explicitly NAMES a specific paper by its title (even embedded in "
    "a longer sentence or mixed Chinese/English, e.g. '帮我找 BERT 那篇预训练论文'), "
    "output THAT paper's title exactly and nothing else — the user wants that one paper.\n"
    "- Prefer the field's canonical terminology over rare synonyms."
)

# 用户消息只放检索诉求本身
_USER = "User input: {nl}\nSearch query:"


def rewrite_query(nl_text: str) -> str:
    """
    自然语言（中/英）→ 英文检索关键词串。

    失败（无 LLM / 无 key / 网络异常 / 空输出）一律返回原始输入，保证不阻断检索。
    """
    nl_text = (nl_text or "").strip()
    if not nl_text or _call_deepseek is None:
        return nl_text

    try:
        raw = _call_deepseek(
            _USER.format(nl=nl_text), max_tokens=60, system=_SYSTEM
        )
    except Exception as e:
        print(f"[改写日志] 查询改写失败，回退原始查询：{e}")
        return nl_text

    # 清洗：取首个非空行，去掉引号/书名号/句号等，压缩空白
    line = next((l.strip() for l in (raw or "").splitlines() if l.strip()), "")
    line = line.strip(" \t\"'`，。.：:；;")
    line = re.sub(r"\s+", " ", line)
    return line or nl_text


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "我想了解大模型如何减少幻觉"
    print(f"原始：{q}")
    print(f"改写：{rewrite_query(q)}")
