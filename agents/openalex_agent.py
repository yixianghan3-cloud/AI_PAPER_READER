# 负责人：2号位（检索扩展 · OpenAlex）
# 描述：用 OpenAlex Works API 检索论文（相关性 + 引用数），返回与 arXiv 检索
#       一致的「论文元数据列表」，供 search_agent 编排。Semantic Scholar 的免审批平替。
# ============================================================
# 为什么用 OpenAlex（替代 Semantic Scholar）：
#   - 完全免费、无需申请 key（S2 申请被拒也不影响）。
#   - 加 mailto 进 "polite pool"，限流很宽（约 10 万请求/天）。
#   - 有引用数(cited_by_count)、开放获取链接、可提取 arXiv id。
# 设计与 semantic_agent 同构：限速 + 429 退避 + 落盘缓存；返回结构对齐 arXiv meta。
#   PDF 衔接：有 arXiv id → arXiv pdf；否则 open access oa_url / location pdf；否则空。
#   建议设环境变量 OPENALEX_MAILTO=你的邮箱（进 polite pool，更稳更快）。
# ============================================================
# -*- coding: utf-8 -*-

import os
import re
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
OA_API_BASE     = "https://api.openalex.org/works"
OA_MAILTO       = os.environ.get("OPENALEX_MAILTO", "")            # 填邮箱进 polite pool（强烈建议）
OA_TIMEOUT      = int(os.environ.get("OPENALEX_TIMEOUT", "30"))
OA_MAX_RETRY    = int(os.environ.get("OPENALEX_MAX_RETRY", "3"))
OA_MIN_INTERVAL = float(os.environ.get("OPENALEX_MIN_INTERVAL", "0.2"))  # OpenAlex 限流宽，间隔可小
OA_RETRY_BASE   = float(os.environ.get("OPENALEX_RETRY_BASE", "2.0"))
OA_CACHE        = os.environ.get("OPENALEX_CACHE", "1") != "0"

# 只取用得上的字段，减小负载（OpenAlex 推荐 select）
OA_SELECT = ("id,display_name,publication_year,authorships,cited_by_count,"
             "abstract_inverted_index,open_access,primary_location,locations,ids")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR    = _PROJECT_ROOT / "cache"
_last_request_ts = 0.0

_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# 限速
# ─────────────────────────────────────────────────────────────
def _respect_rate_limit():
    global _last_request_ts
    wait = OA_MIN_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


# ─────────────────────────────────────────────────────────────
# 缓存（前缀 search_oa_，与 arXiv / S2 缓存区分）
# ─────────────────────────────────────────────────────────────
def _cache_path(query: str, max_results: int) -> Path:
    raw = f"oa|{query.strip().lower()}|{max_results}".encode("utf-8")
    return _CACHE_DIR / f"search_oa_{hashlib.md5(raw).hexdigest()}.json"


def _load_cache(query: str, max_results: int):
    if not OA_CACHE:
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
    if not OA_CACHE:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_cache_path(query, max_results), "w", encoding="utf-8") as f:
            json.dump(meta_list, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────
# 带重试 / 限速的请求
# ─────────────────────────────────────────────────────────────
def _fetch_oa(url: str) -> dict:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    # polite pool：User-Agent 带 mailto；OpenAlex 据此给更稳的配额
    ua = "AI_Paper_Reader/1.0" + (f" (mailto:{OA_MAILTO})" if OA_MAILTO else "")
    headers = {"User-Agent": ua}

    last_err = None
    for attempt in range(1, OA_MAX_RETRY + 1):
        _respect_rate_limit()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=OA_TIMEOUT, context=ssl_context) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                if retry_after and str(retry_after).strip().isdigit():
                    wait = float(retry_after)
                else:
                    wait = OA_RETRY_BASE * (2 ** (attempt - 1))
                print(f"[OpenAlex日志] 返回 {e.code}，{wait:.0f}s 后重试 ({attempt}/{OA_MAX_RETRY})"
                      f"{'（建议设 OPENALEX_MAILTO 进 polite pool）' if e.code == 429 and not OA_MAILTO else ''}")
                if attempt < OA_MAX_RETRY:
                    time.sleep(wait)
                    continue
            else:
                raise RuntimeError(f"OpenAlex 请求失败：HTTP {e.code}") from e
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            last_err = f"超时/连接错误：{reason}"
            print(f"[OpenAlex日志] 请求超时/失败，{OA_RETRY_BASE:.0f}s 后重试 ({attempt}/{OA_MAX_RETRY})：{reason}")
            if attempt < OA_MAX_RETRY:
                time.sleep(OA_RETRY_BASE)
                continue

    raise RuntimeError(f"OpenAlex 请求失败（已重试 {OA_MAX_RETRY} 次）：{last_err}")


# ─────────────────────────────────────────────────────────────
# 工具：重建 abstract（OpenAlex 给的是倒排索引）+ 提取 arXiv id
# ─────────────────────────────────────────────────────────────
def _reconstruct_abstract(inv: dict) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    if not pos:
        return ""
    return " ".join(pos[i] for i in sorted(pos))


def _extract_arxiv_id(work: dict) -> str:
    cands = []
    pl = work.get("primary_location") or {}
    cands += [pl.get("landing_page_url"), pl.get("pdf_url")]
    for loc in (work.get("locations") or []):
        cands += [loc.get("landing_page_url"), loc.get("pdf_url")]
    for u in cands:
        if u:
            m = _ARXIV_RE.search(u)
            if m:
                return m.group(1)
    return ""


# ─────────────────────────────────────────────────────────────
# OpenAlex work → 统一 meta（对齐 arXiv meta 结构）
# ─────────────────────────────────────────────────────────────
def _to_meta(work: dict) -> dict:
    arxiv_id = _extract_arxiv_id(work)
    oa = work.get("open_access") or {}
    # location 里的 pdf 兜底
    loc_pdf = ""
    pl = work.get("primary_location") or {}
    if pl.get("pdf_url"):
        loc_pdf = pl["pdf_url"]
    else:
        for loc in (work.get("locations") or []):
            if loc.get("pdf_url"):
                loc_pdf = loc["pdf_url"]
                break

    if arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    elif oa.get("oa_url"):
        pdf_url = oa["oa_url"]
    elif loc_pdf:
        pdf_url = loc_pdf
    else:
        pdf_url = ""

    title = (work.get("display_name") or "").replace("\n", " ").strip()
    file_id = arxiv_id or ("oa_" + hashlib.md5(
        (work.get("id") or title).encode("utf-8")).hexdigest()[:12])

    return {
        "title":          title,
        "authors":        [(a.get("author") or {}).get("display_name", "")
                           for a in (work.get("authorships") or [])],
        "year":           work.get("publication_year") or 0,
        "abstract":       _reconstruct_abstract(work.get("abstract_inverted_index")),
        "pdf_url":        pdf_url,
        "arxiv_id":       file_id,
        "source":         "openalex",
        "citation_count": work.get("cited_by_count") or 0,
    }


# ─────────────────────────────────────────────────────────────
# 对外：检索（返回 meta 列表，已按引用数降序）
# ─────────────────────────────────────────────────────────────
def openalex_search(query: str, max_results: int = 5) -> list:
    """
    用 OpenAlex 检索论文，返回论文元数据列表（按引用数降序）。
    字段对齐 arXiv meta：title/authors/year/abstract/pdf_url/arxiv_id/source（另带 citation_count）。
    """
    if not query.strip():
        return []

    cached = _load_cache(query, max_results)
    if cached is not None:
        print(f"[OpenAlex日志] 命中检索缓存: {query}（{len(cached)} 篇）")
        return cached

    # 多取候选再本地按引用数精排（OpenAlex search 默认按相关性）
    per_page = max(max_results, min(max_results * 3, 50))
    params = {
        "search": query,
        "per-page": str(per_page),
        "select": OA_SELECT,
    }
    if OA_MAILTO:
        params["mailto"] = OA_MAILTO
    url = f"{OA_API_BASE}?{urllib.parse.urlencode(params)}"
    print(f"[OpenAlex日志] 正在检索 OpenAlex: {query}")

    data = _fetch_oa(url)
    works = data.get("results") or []
    metas = [_to_meta(w) for w in works if w.get("display_name")]

    # 按引用数降序（"挑高质量"）。TODO：可加相关性加权 / 年份 / 领域过滤。
    metas.sort(key=lambda m: m.get("citation_count", 0), reverse=True)
    metas = metas[:max_results]

    if metas:
        _save_cache(query, max_results, metas)
    else:
        print("[OpenAlex日志] 未检索到相关论文。")
    return metas


# ─────────────────────────────────────────────────────────────
# 命令行自测：python agents/openalex_agent.py "your query"
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "retrieval augmented generation"
    rs = openalex_search(q, max_results=3)
    print(f"检索到 {len(rs)} 篇：")
    for r in rs:
        print(f"  - [{r['citation_count']}引] {r['title'][:56]} | pdf:{bool(r['pdf_url'])} | arxiv:{r['arxiv_id']}")
