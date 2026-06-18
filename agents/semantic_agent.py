# 负责人：2号位（检索扩展 · Semantic Scholar）
# 描述：用 Semantic Scholar Graph API 检索论文（相关性 + 引用数 + TLDR），
#       返回与 arXiv 检索一致的「论文元数据列表」，供 search_agent 编排。
# ============================================================
# 设计要点（骨架版，标 TODO 处留给后续完善）：
#   - 返回结构对齐 search_agent 的 meta：title/authors/year/abstract/pdf_url/arxiv_id
#     额外带 citation_count / tldr / source，供排序与展示。
#   - PDF 可得性是关键：S2 很多论文没有开放 PDF。
#       优先级：有 arXiv id → 用 arXiv pdf 链接（后续走 arXiv 下载）
#               否则 openAccessPdf.url → 直链
#               都没有 → pdf_url=""（上游 safe_parse 会用 abstract 兜底）
#   - 复用 search_agent 同款：限速 + 429 指数退避 + 缓存。
#   - S2 无 key 限流很凶（共享池易 429）。强烈建议申请免费 key：
#       https://www.semanticscholar.org/product/api  → 设环境变量 S2_API_KEY
# ============================================================
# -*- coding: utf-8 -*-

import os
import json
import time
import ssl
import socket
import hashlib
import certifi
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ── 可配置项（环境变量可覆盖）──────────────────────────────
S2_API_BASE     = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_API_KEY      = os.environ.get("S2_API_KEY", "")               # 留好 key 位：有则走 x-api-key 头，限流大幅放宽
S2_TIMEOUT      = int(os.environ.get("S2_TIMEOUT", "30"))
S2_MAX_RETRY    = int(os.environ.get("S2_MAX_RETRY", "3"))
S2_MIN_INTERVAL = float(os.environ.get("S2_MIN_INTERVAL", "1.0"))  # 无 key 时建议调大（如 3.0）
S2_RETRY_BASE   = float(os.environ.get("S2_RETRY_BASE", "3.0"))
S2_CACHE        = os.environ.get("S2_CACHE", "1") != "0"

# 拉取字段（按需增减；tldr/citationCount 用于排序与展示）
S2_FIELDS = "title,abstract,year,authors,externalIds,openAccessPdf,citationCount,tldr"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR    = _PROJECT_ROOT / "cache"
_last_request_ts = 0.0


# ─────────────────────────────────────────────────────────────
# 限速（与 search_agent 同款）
# ─────────────────────────────────────────────────────────────
def _respect_rate_limit():
    global _last_request_ts
    wait = S2_MIN_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


# ─────────────────────────────────────────────────────────────
# 缓存（按 query + max_results，前缀 s2_ 与 arXiv 缓存区分）
# ─────────────────────────────────────────────────────────────
def _cache_path(query: str, max_results: int) -> Path:
    raw = f"s2|{query.strip().lower()}|{max_results}".encode("utf-8")
    return _CACHE_DIR / f"search_s2_{hashlib.md5(raw).hexdigest()}.json"


def _load_cache(query: str, max_results: int):
    if not S2_CACHE:
        return None
    p = _cache_path(query, max_results)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _save_cache(query: str, max_results: int, meta_list: list) -> None:
    if not S2_CACHE:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_cache_path(query, max_results), "w", encoding="utf-8") as f:
            json.dump(meta_list, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────
# 带重试 / 限速的 S2 请求
# ─────────────────────────────────────────────────────────────
def _fetch_s2(url: str) -> dict:
    """请求 S2，429/5xx 指数退避、超时快速重试。最终失败抛 RuntimeError。"""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    headers = {"User-Agent": "AI_Paper_Reader/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    last_err = None
    for attempt in range(1, S2_MAX_RETRY + 1):
        _respect_rate_limit()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=S2_TIMEOUT, context=ssl_context) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                if retry_after and str(retry_after).strip().isdigit():
                    wait = float(retry_after)
                else:
                    wait = S2_RETRY_BASE * (2 ** (attempt - 1))
                print(f"[S2日志] 返回 {e.code}（限流/服务端），{wait:.0f}s 后重试 ({attempt}/{S2_MAX_RETRY})"
                      f"{'（建议申请 S2_API_KEY 提额）' if e.code == 429 and not S2_API_KEY else ''}")
                if attempt < S2_MAX_RETRY:
                    time.sleep(wait)
                    continue
            else:
                raise RuntimeError(f"Semantic Scholar 请求失败：HTTP {e.code}") from e
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            last_err = f"超时/连接错误：{reason}"
            print(f"[S2日志] 请求超时/失败，{S2_RETRY_BASE:.0f}s 后重试 ({attempt}/{S2_MAX_RETRY})：{reason}")
            if attempt < S2_MAX_RETRY:
                time.sleep(S2_RETRY_BASE)
                continue

    raise RuntimeError(f"Semantic Scholar 请求失败（已重试 {S2_MAX_RETRY} 次）：{last_err}")


# ─────────────────────────────────────────────────────────────
# S2 paper → 统一 meta（与 search_agent._parse_entries 的结构对齐）
# ─────────────────────────────────────────────────────────────
def _to_meta(paper: dict) -> dict:
    ext = paper.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv") or ""                       # 如 "2401.15391"
    oa = paper.get("openAccessPdf") or {}
    tldr = (paper.get("tldr") or {}).get("text") or ""

    # PDF 链接优先级：arXiv > openAccessPdf > 空
    if arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    elif oa.get("url"):
        pdf_url = oa["url"]
    else:
        pdf_url = ""

    # arxiv_id 仅内部用于 PDF 文件命名；S2 无 arXiv 版时给个稳定 fallback id
    file_id = arxiv_id or ("s2_" + (paper.get("paperId") or hashlib.md5(
        (paper.get("title") or "").encode("utf-8")).hexdigest())[:12])

    return {
        "title":          (paper.get("title") or "").replace("\n", " ").strip(),
        "authors":        [a.get("name", "") for a in (paper.get("authors") or [])],
        "year":           paper.get("year") or 0,
        "abstract":       (paper.get("abstract") or tldr or "").replace("\n", " ").strip(),
        "pdf_url":        pdf_url,
        "arxiv_id":       file_id,
        "source":         "semantic_scholar",
        # —— 额外字段（不在契约里，但可用于排序/展示）——
        "citation_count": paper.get("citationCount") or 0,
        "tldr":           tldr,
    }


# ─────────────────────────────────────────────────────────────
# 对外：检索（返回 meta 列表，供 search_agent 编排下载/拼装）
# ─────────────────────────────────────────────────────────────
def semantic_search(query: str, max_results: int = 5) -> list:
    """
    用 Semantic Scholar 检索论文，返回论文元数据列表（已按引用数降序）。

    返回的每个 dict 字段对齐 arXiv meta：
        title / authors / year / abstract / pdf_url / arxiv_id / source
        （另带 citation_count / tldr）

    Raises:
        RuntimeError: 网络/限流彻底失败时。无结果返回 []。
    """
    if not query.strip():
        return []

    cached = _load_cache(query, max_results)
    if cached is not None:
        print(f"[S2日志] 命中检索缓存: {query}（{len(cached)} 篇）")
        return cached

    # TODO(组员)：可多取一些候选再按引用数/相关性精排；如需更强排序可换 bulk 端点。
    limit = max(max_results, min(max_results * 3, 100))   # 多取候选，便于本地精排
    url = (f"{S2_API_BASE}?query={urllib.parse.quote(query)}"
           f"&limit={limit}&fields={S2_FIELDS}")
    print(f"[S2日志] 正在检索 Semantic Scholar: {query}")

    data = _fetch_s2(url)
    papers = data.get("data") or []
    metas = [_to_meta(p) for p in papers if p.get("title")]

    # 按引用数降序（"挑高质量"）。TODO：可加入相关性加权、年份过滤、领域过滤。
    metas.sort(key=lambda m: m.get("citation_count", 0), reverse=True)
    metas = metas[:max_results]

    if metas:
        _save_cache(query, max_results, metas)
    else:
        print("[S2日志] 未检索到相关论文。")
    return metas


# ─────────────────────────────────────────────────────────────
# 命令行自测：python agents/semantic_agent.py "your query"
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "retrieval augmented generation"
    rs = semantic_search(q, max_results=3)
    print(f"检索到 {len(rs)} 篇：")
    for r in rs:
        print(f"  - [{r['citation_count']}引] {r['title'][:60]} | pdf:{bool(r['pdf_url'])} | arxiv:{r['arxiv_id']}")
