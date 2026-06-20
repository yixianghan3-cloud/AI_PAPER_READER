# 负责人：2号位（Agent 搜索 / 文献爬取）
# 描述：调用 arXiv API 搜索论文，并自动下载 PDF 到本地
# ============================================================
# v1.1 变更（针对国内访问 export.arxiv.org 不稳 / 限流）：
#   1. 【重试】API 请求失败按错误类型分别处理：
#        - 429 限流 / 5xx → 指数退避（尊重 Retry-After 头），不猛打
#        - 超时 / 连接错误 → 短间隔快速重试
#   2. 【限速】全局保证 arXiv API 请求间隔 ≥ ARXIV_MIN_INTERVAL（默认 3s），
#      遵守官方“每 3 秒不超过 1 次”，从源头减少 429。
#   3. 【检索缓存】按 (query, max_results) 落盘缓存论文元数据，命中则
#      跳过 API 请求 —— 演示前预热后，当天不再依赖外网（外网挂了也能出结果）。
#   4. 【可配置】超时 / 重试次数 / 限速间隔 / 缓存开关均支持环境变量覆盖。
#   契约不变：函数名 search_papers、参数、返回字段均不改。
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
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

# 可选扩展模块（容错 import：模块缺失/出错都不影响纯 arXiv 主流程）
try:
    from agents.openalex_agent import openalex_search
except Exception:
    openalex_search = None
try:
    from agents.semantic_agent import semantic_search
except Exception:
    semantic_search = None
try:
    from agents.query_rewriter import rewrite_query
except Exception:
    rewrite_query = None

# ── 可配置项（环境变量可覆盖）──────────────────────────────
ARXIV_TIMEOUT      = int(os.environ.get("ARXIV_TIMEOUT", "30"))         # API 请求超时（秒）
ARXIV_PDF_TIMEOUT  = int(os.environ.get("ARXIV_PDF_TIMEOUT", "30"))     # PDF 下载超时（秒）
ARXIV_MAX_RETRY    = int(os.environ.get("ARXIV_MAX_RETRY", "3"))        # 最大重试次数
ARXIV_MIN_INTERVAL = float(os.environ.get("ARXIV_MIN_INTERVAL", "3.0")) # 两次 API 请求最小间隔（秒）
ARXIV_RETRY_BASE   = float(os.environ.get("ARXIV_RETRY_BASE", "3.0"))   # 退避基数（秒）
SEARCH_CACHE       = os.environ.get("ARXIV_SEARCH_CACHE", "1") != "0"   # 检索缓存开关
SEARCH_CACHE_TTL   = int(os.environ.get("ARXIV_SEARCH_CACHE_TTL", "0")) # 缓存有效期（秒），0 = 永不过期

# ── 检索增强开关（默认关，保持纯 arXiv 行为；按需逐步启用）──────
USE_OPENALEX       = os.environ.get("USE_OPENALEX", "0") != "0"      # 1=用 OpenAlex 检索（S2 免审批平替，推荐）
USE_SEMANTIC       = os.environ.get("USE_SEMANTIC", "0") != "0"      # 1=用 Semantic Scholar 检索（需 key）
USE_QUERY_REWRITE  = os.environ.get("USE_QUERY_REWRITE", "0") != "0" # 1=检索前用 LLM 改写自然语言
# 当非 arXiv 来源（如 OpenAlex）给的 PDF 链接下载失败时，用标题去 arXiv 找可下载版本兜底。
# 仅在「非 arXiv 直链」时触发，对每篇至多多一次 arXiv 查询（已限速）。设 0 关闭。
ARXIV_TITLE_FALLBACK = os.environ.get("ARXIV_TITLE_FALLBACK", "1") != "0"
# 兜底查询用更短超时/更少重试，失败就尽快降级摘要，不让用户干等。
ARXIV_FALLBACK_TIMEOUT = int(os.environ.get("ARXIV_FALLBACK_TIMEOUT", "12"))
ARXIV_FALLBACK_RETRY   = int(os.environ.get("ARXIV_FALLBACK_RETRY", "1"))
# 已知反爬 / 拒绝程序化下载的域名：直接跳过注定失败的首次下载，省掉等待。
_BLOCKED_PDF_HOSTS = ("ojs.aaai.org",)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR    = _PROJECT_ROOT / "cache"
_API_BASE     = "https://export.arxiv.org/api/query"
_HEADERS      = {"User-Agent": "AI_Paper_Reader/1.0"}

_last_request_ts = 0.0   # 模块级：上次 API 请求时间戳（限速用）


# 工具函数：安全提取 XML 文本，防止 None 报错
def _text(element, default=""):
    return element.text.strip() if (element is not None and element.text) else default


# ─────────────────────────────────────────────────────────────
# 限速：遵守 arXiv “每 3 秒不超过 1 次”
# ─────────────────────────────────────────────────────────────
def _respect_rate_limit():
    """阻塞到距上次 API 请求满 ARXIV_MIN_INTERVAL 秒，再放行。"""
    global _last_request_ts
    wait = ARXIV_MIN_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


# ─────────────────────────────────────────────────────────────
# 检索结果缓存（按 query + max_results）
# ─────────────────────────────────────────────────────────────
def _search_cache_path(query: str, max_results: int, source: str = "arxiv") -> Path:
    base = f"{query.strip().lower()}|{max_results}"
    if source != "arxiv":                       # arxiv 不加前缀，兼容已有缓存文件
        base = f"{source}|{base}"
    return _CACHE_DIR / f"search_{hashlib.md5(base.encode('utf-8')).hexdigest()}.json"


def _load_search_cache(query: str, max_results: int, source: str = "arxiv"):
    """命中且有效则返回论文元数据列表；否则返回 None。"""
    if not SEARCH_CACHE:
        return None
    p = _search_cache_path(query, max_results, source)
    if not p.exists():
        return None
    try:
        if SEARCH_CACHE_TTL > 0 and (time.time() - p.stat().st_mtime) > SEARCH_CACHE_TTL:
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else None
    except Exception:
        return None   # 缓存损坏当作未命中


def _save_search_cache(query: str, max_results: int, meta_list: list, source: str = "arxiv") -> None:
    """把论文元数据列表写入缓存（尽力而为，写失败不影响主流程）。"""
    if not SEARCH_CACHE:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_search_cache_path(query, max_results, source), "w", encoding="utf-8") as f:
            json.dump(meta_list, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────
# 带重试 / 限速的 arXiv API 请求
# ─────────────────────────────────────────────────────────────
def _fetch_arxiv(url: str, timeout: int = None, max_retry: int = None) -> bytes:
    """
    请求 arXiv API，按错误类型重试：
      - 429 / 5xx：指数退避（尊重 Retry-After），不猛打
      - 超时 / 连接错误：短间隔快速重试
    最终仍失败抛 RuntimeError（附可读信息）。
    timeout / max_retry 不传则用模块默认；兜底查询会传更短预算以「快速失败」。
    """
    timeout   = timeout   or ARXIV_TIMEOUT
    max_retry = max_retry or ARXIV_MAX_RETRY
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    last_err = None

    for attempt in range(1, max_retry + 1):
        _respect_rate_limit()
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
                return resp.read()

        except urllib.error.HTTPError as e:
            # 注意：HTTPError 是 URLError 子类，必须先于 URLError 捕获
            last_err = f"HTTP {e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                if retry_after and str(retry_after).strip().isdigit():
                    wait = float(retry_after)
                else:
                    wait = ARXIV_RETRY_BASE * (2 ** (attempt - 1))   # 指数退避
                print(f"[2号位日志] arXiv 返回 {e.code}（限流/服务端），{wait:.0f}s 后重试 ({attempt}/{max_retry})")
                if attempt < max_retry:
                    time.sleep(wait)
                    continue
            else:
                # 其余 4xx（如 400/404）重试无意义，直接抛
                raise RuntimeError(f"arXiv API 请求失败：HTTP {e.code}") from e

        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            last_err = f"超时/连接错误：{reason}"
            print(f"[2号位日志] 请求超时/失败，{ARXIV_RETRY_BASE:.0f}s 后重试 ({attempt}/{max_retry})：{reason}")
            if attempt < max_retry:
                time.sleep(ARXIV_RETRY_BASE)
                continue

    raise RuntimeError(f"arXiv API 请求失败（已重试 {max_retry} 次）：{last_err}")


# ─────────────────────────────────────────────────────────────
# 解析 arXiv 返回的 Atom XML → 论文元数据列表
# ─────────────────────────────────────────────────────────────
def _parse_entries(xml_data: bytes) -> list:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise RuntimeError("解析 arXiv 返回的数据失败，接口可能发生了变动。") from e

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    metas = []
    for i, entry in enumerate(root.findall('atom:entry', ns)):
        title = _text(entry.find('atom:title', ns)).replace('\n', ' ')
        authors = [_text(a.find('atom:name', ns)) for a in entry.findall('atom:author', ns)]
        published = _text(entry.find('atom:published', ns))
        try:
            year = int(published[:4]) if published else 0
        except ValueError:
            year = 0
        abstract = _text(entry.find('atom:summary', ns)).replace('\n', ' ')

        id_url = _text(entry.find('atom:id', ns))
        arxiv_id = id_url.split('/')[-1] if id_url else f"unknown_id_{i}"

        pdf_url = ""
        for link in entry.findall('atom:link', ns):
            if link.attrib.get('title') == 'pdf' or link.attrib.get('type') == 'application/pdf':
                pdf_url = link.attrib.get('href')
                break
        if pdf_url and pdf_url.startswith('http://'):
            pdf_url = pdf_url.replace('http://', 'https://')

        metas.append({
            "title": title,
            "authors": authors,
            "year": year,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id,   # 仅内部用于 PDF 命名，不进最终返回
        })
    return metas


# ─────────────────────────────────────────────────────────────
# 下载单篇 PDF（已存在则跳过）；失败返回 ""
# ─────────────────────────────────────────────────────────────
def _norm_title(s: str) -> str:
    """标题归一化（仅留小写字母数字 + 单空格），用于相似度比对。"""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# 标题→arXiv 解析结果缓存（含「无 arXiv 版」的负缓存），避免重复打 arXiv 招限流
_TITLE_MAP_PATH = _CACHE_DIR / "arxiv_title_map.json"
_title_map = None


def _title_map_load() -> dict:
    global _title_map
    if _title_map is None:
        try:
            with open(_TITLE_MAP_PATH, encoding="utf-8") as f:
                _title_map = json.load(f)
            if not isinstance(_title_map, dict):
                _title_map = {}
        except Exception:
            _title_map = {}
    return _title_map


def _title_map_save() -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_TITLE_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(_title_map, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _arxiv_pdf_by_title(title: str):
    """
    用标题在 arXiv 搜一篇；标题高度吻合（Jaccard≥0.8 或互相包含）才返回
    (arxiv_id, pdf_url)，否则 (None, None)。防止 OpenAlex 链接失效时下错论文。

    结果（含「无 arXiv 版」）落盘缓存：同一标题不再重复打 arXiv。
    查询用更短超时/更少重试（ARXIV_FALLBACK_*），失败尽快降级。
    """
    title = (title or "").strip()
    if not title:
        return None, None

    key = _norm_title(title)
    cache = _title_map_load()
    if key in cache:                                  # 命中（正/负）缓存，秒回
        v = cache[key]
        return (v[0], v[1]) if v else (None, None)

    result = None                                     # None = 无可用 arXiv 版（负缓存）
    try:
        q = urllib.parse.quote(f'"{title}"')
        url = f"{_API_BASE}?search_query=ti:{q}&start=0&max_results=1"
        metas = _parse_entries(_fetch_arxiv(
            url, timeout=ARXIV_FALLBACK_TIMEOUT, max_retry=ARXIV_FALLBACK_RETRY))
        if metas:
            cand = metas[0]
            a, b = key, _norm_title(cand.get("title", ""))
            if a and b:
                sa, sb = set(a.split()), set(b.split())
                jac = len(sa & sb) / max(1, len(sa | sb))
                if jac >= 0.8 or a in b or b in a:
                    result = [cand.get("arxiv_id"), cand.get("pdf_url")]
                else:
                    print(f"[2号位日志] arXiv 兜底命中标题不够吻合（jac={jac:.2f}），放弃：{cand.get('title','')[:50]}")
    except Exception as e:
        # 查询本身失败（超时/限流）不写负缓存：可能只是暂时性，下次还可重试
        print(f"[2号位日志] arXiv 标题兜底查询失败（快速降级）：{e}")
        return None, None

    cache[key] = result                               # 命中或确认无版本，均落盘
    _title_map_save()
    return (result[0], result[1]) if result else (None, None)


def _try_download(pdf_url: str, local_path: Path, ssl_context) -> bool:
    """下载 pdf_url 到 local_path 并校验是真 PDF；成功 True，失败清理残file 返回 False。"""
    try:
        pdf_req = urllib.request.Request(pdf_url, headers=_HEADERS)
        with urllib.request.urlopen(pdf_req, timeout=ARXIV_PDF_TIMEOUT, context=ssl_context) as r, open(local_path, 'wb') as f:
            shutil.copyfileobj(r, f)
        with open(local_path, 'rb') as f:
            if f.read(4) != b'%PDF':
                raise ValueError("下载的文件非有效 PDF 格式")
        time.sleep(1)   # 下载也对服务器施压，留个间隔
        return True
    except Exception as e:
        print(f"[2号位日志] ⚠️ 单篇下载失败: {pdf_url[:70]} | 错误: {e}")
        if local_path.exists():
            local_path.unlink()
        return False


def _download_pdf(meta: dict, download_dir: Path, ssl_context) -> str:
    # .strip() 去首尾空格；截断后再 strip，避免 Windows 路径尾部空格被 trim 导致
    # MinerU 输出目录 FileNotFoundError（[WinError 3]）。
    safe_title = re.sub(r'[\\/*?:"<>|]', "", meta["title"]).strip()[:40].strip()
    pdf_url = meta.get("pdf_url", "")
    # 已知反爬域名：跳过注定失败的首次下载，直接走下方 arXiv 兜底
    blocked = any(h in pdf_url.lower() for h in _BLOCKED_PDF_HOSTS)
    if blocked:
        print(f"[2号位日志] 跳过已知反爬域名，直接走 arXiv 兜底: {meta['title'][:50]}")

    # 1) 先试 meta 自带链接（OpenAlex 可能给出版商链，未必能程序化下载）
    if pdf_url and not blocked:
        file_name = f"{meta['arxiv_id']}_{safe_title}.pdf"
        local_path = download_dir / file_name
        if local_path.exists() and local_path.stat().st_size > 1024:
            print(f"[2号位日志] 论文已存在，跳过下载: {file_name}")
            return str(local_path)
        print(f"[2号位日志] 正在下载 PDF: {file_name} ...")
        if _try_download(pdf_url, local_path, ssl_context):
            return str(local_path)

    # 2) 兜底：链接缺失或下载失败，且原链非 arXiv 直链 → 用标题去 arXiv 找可下载版本
    #    （修复如 Informer 这类「有 arXiv 版但 OpenAlex 只给被反爬的出版商链」的论文）
    if ARXIV_TITLE_FALLBACK and "arxiv.org" not in pdf_url.lower():
        aid, a_pdf = _arxiv_pdf_by_title(meta.get("title", ""))
        if aid and a_pdf:
            file_name = f"{aid}_{safe_title}.pdf"
            local_path = download_dir / file_name
            if local_path.exists() and local_path.stat().st_size > 1024:
                return str(local_path)
            print(f"[2号位日志] 改用 arXiv 兜底下载: {aid}")
            if _try_download(a_pdf, local_path, ssl_context):
                return str(local_path)

    return ""


# ─────────────────────────────────────────────────────────────
# 按查询意图建议返回篇数（用原始查询判定，最贴近用户意图）
#   英文精确标题 → 2（用户要那一篇，少而精）
#   中文长句 / 探索描述 → 5（话题探索，多给候选）
#   普通英文关键词 → 4（折中）
# ─────────────────────────────────────────────────────────────
def suggest_max_results(query: str) -> int:
    q = (query or "").strip()
    if not q:
        return 3
    has_cjk = bool(re.search(r"[一-鿿]", q))
    words = q.split()
    n = len(words)
    caps = sum(1 for w in words if w[:1].isupper())
    if has_cjk:                                  # 中文：多为话题/探索
        return 5 if len(q) >= 6 else 4
    if (":" in q) or (n >= 5) or (caps >= 2 and n >= 3):  # 英文像具体论文标题
        return 2
    return 4                                     # 英文短关键词：话题


# ─────────────────────────────────────────────────────────────
# 对外契约函数（名称 / 参数 / 返回字段均不可改）
# ─────────────────────────────────────────────────────────────
def search_papers(query: str, max_results: int = 5, auto_count: bool = False) -> list[dict]:
    """
    根据关键词调用 arXiv API 搜索学术论文，并将 PDF 下载到本地。

    超时/限流时自动重试，搜过的词命中检索缓存可跳过 API 请求。
    auto_count=True 时，按原始查询意图自动决定返回篇数（忽略传入的 max_results）。
    """
    if not query.strip():
        raise ValueError("query 不能为空")

    # auto：用原始查询判定篇数（须在改写覆盖 query 之前取）
    if auto_count:
        max_results = suggest_max_results(query)
        print(f"[2号位日志] 自动篇数：{query!r} → {max_results} 篇")

    download_dir = _PROJECT_ROOT / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    # 0. 查询改写（可选）：自然语言 → 英文检索词。失败自动回退原文，不阻断。
    if USE_QUERY_REWRITE and rewrite_query:
        rewritten = rewrite_query(query)
        if rewritten and rewritten.strip() and rewritten != query:
            print(f"[2号位日志] 查询改写：{query!r} → {rewritten!r}")
            query = rewritten

    # 检索来源优先级：OpenAlex（推荐）> Semantic Scholar > arXiv
    use_oa = USE_OPENALEX and (openalex_search is not None)
    use_s2 = (not use_oa) and USE_SEMANTIC and (semantic_search is not None)
    source = "oa" if use_oa else ("s2" if use_s2 else "arxiv")

    # 1. 先查检索缓存：命中则跳过 API 请求（最易超时/限流的一步）
    meta_list = _load_search_cache(query, max_results, source)
    if meta_list is not None:
        print(f"[2号位日志] 命中检索缓存[{source}]: {query}（{len(meta_list)} 篇）")
    else:
        if use_oa:
            # OpenAlex 选题 + 引用排序；PDF 仍优先走下方 arXiv 下载（meta 已带 pdf_url）
            meta_list = openalex_search(query, max_results)
        elif use_s2:
            # S2 选题 + 引用排序；PDF 仍优先走下方 arXiv 下载（meta 已带 pdf_url）
            meta_list = semantic_search(query, max_results)
        else:
            terms = query.strip().split()
            search_query = "+AND+".join(f"all:{urllib.parse.quote(t)}" for t in terms)
            url = f"{_API_BASE}?search_query={search_query}&start=0&max_results={max_results}"
            print(f"[2号位日志] 正在搜索 arXiv: {query}")
            xml_data = _fetch_arxiv(url)
            meta_list = _parse_entries(xml_data)
        if meta_list:
            _save_search_cache(query, max_results, meta_list, source)

    if not meta_list:
        print("[2号位日志] 未搜索到相关论文。")
        return []

    # 2. 逐篇下载 PDF（已存在则跳过），拼出契约要求的返回结构
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    papers_list = []
    for meta in meta_list:
        local_path_str = _download_pdf(meta, download_dir, ssl_context)
        papers_list.append({
            "title": meta["title"],
            "authors": meta["authors"],
            "year": meta["year"],
            "abstract": meta["abstract"],
            "pdf_url": meta["pdf_url"],
            "local_path": local_path_str,
            "source": meta.get("source", "arxiv"),
        })

    return papers_list
