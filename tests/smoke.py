# ============================================================
# tests/smoke.py — 冒烟测试（纯逻辑回归，无需网络 / API key）
# ------------------------------------------------------------
# 目的：以后改检索/解析/摘要的核心逻辑后，一条命令快速验证没回归。
# 跑法：  python tests/smoke.py        （退出码 0=全过，非 0=有失败）
# 覆盖：自动篇数意图判定 / OpenAlex 去重合并 / 查询改写回退 /
#       PDF 后处理与批量入口 / arXiv 标题兜底缓存（命中不打网络）
# 不覆盖：真实 MinerU、真实 DeepSeek、真实联网检索（那些靠手测/缓存）
# ============================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


# ── 1. 自动篇数：按查询意图分桶 ─────────────────────────────
from agents.search_agent import suggest_max_results as smr

check("自动篇数 英文精确标题→2", smr("Attention Is All You Need") == 2)
check("自动篇数 中文长句→5",     smr("我想了解大模型如何减少幻觉") == 5)
check("自动篇数 短英文词→4",     smr("diffusion models") == 4)

# ── 2. OpenAlex 去重合并：同篇多记录合并，优选可下载源 ──────
from agents.openalex_agent import _dedup_merge, _pdf_rank

check("PDF打分 arXiv > 反爬域名", _pdf_rank("https://arxiv.org/pdf/x") > _pdf_rank("https://ojs.aaai.org/x"))
_dup = [
    {"title": "Same Paper Title", "citation_count": 100,
     "pdf_url": "https://ojs.aaai.org/a", "arxiv_id": "oa", "abstract": "a"},
    {"title": "Same Paper Title", "citation_count": 10,
     "pdf_url": "https://arxiv.org/pdf/1", "arxiv_id": "1", "abstract": "longer abstract here"},
]
_m = _dedup_merge(_dup)
check("去重 两条合并成一条", len(_m) == 1)
check("去重 引用取最大(100)", _m[0]["citation_count"] == 100)
check("去重 PDF优选arXiv直链", "arxiv.org" in _m[0]["pdf_url"])
check("去重 摘要取更长者",     _m[0]["abstract"] == "longer abstract here")

# ── 3. 查询改写：无 LLM 时回退原文（不阻断检索）─────────────
import agents.query_rewriter as QR

_save = QR._call_deepseek
QR._call_deepseek = None
try:
    check("改写 无LLM回退原文", QR.rewrite_query("transformer") == "transformer")
finally:
    QR._call_deepseek = _save

# ── 4. PDF 后处理 / 批量入口 ────────────────────────────────
from agents.pdf_parser import _assemble_doc, parse_pdfs

_doc = _assemble_doc("# Title\n## Intro\nhello world\n## Method\nfoo bar", "mineru")
check("后处理 提取标题",   _doc and _doc["title"] == "Title")
check("后处理 切出多章节", _doc and len(_doc["sections"]) >= 2)
check("后处理 空正文→None", _assemble_doc("   ", "mineru") is None)
check("批量 缺文件→None项", parse_pdfs(["/no/such/file.pdf"]) == [None])

# ── 5. arXiv 标题兜底缓存：命中直接返回，不打网络 ──────────
import agents.search_agent as SA

SA._title_map_load()
SA._title_map[SA._norm_title("Cached Paper")] = ["1111.2222", "https://arxiv.org/pdf/1111.2222"]
SA._title_map[SA._norm_title("No Arxiv Paper")] = None        # 负缓存
check("兜底 正缓存命中", SA._arxiv_pdf_by_title("Cached Paper") == ("1111.2222", "https://arxiv.org/pdf/1111.2222"))
check("兜底 负缓存命中→None", SA._arxiv_pdf_by_title("No Arxiv Paper") == (None, None))


# ── 汇总 ────────────────────────────────────────────────────
print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
