# ============================================================
# v1.5 变更记录（相对 v1.4）：
#   [契约修复] structured_summary 改为字段级兜底，杜绝缺 key 时
#              1号位拿到不完整 dict 导致 KeyError
#   [防炸]     _call_deepseek 增加 None/空内容防护，避免 json.loads(None)
#              抛 TypeError 绕过 JSONDecodeError
#   [防炸]     Reduce 阶段单独调大 max_tokens=4096，避免长论文输出被截断
#   [健壮]     错误分类改用 SDK 异常类型，替代脆弱的字符串匹配
#   [健壮]     429 限流改为指数退避重试，而非直接 fail-fast
#   [稳定]     固定 temperature=0.2，保证同一论文摘要可复现
#   [性能]     client 改为模块级单例，复用连接
#   [体验]     增加文件级缓存，按 (full_text, lang) 命中则跳过 API 调用
#   [防御]     _safe_json_loads 兜底去围栏 + 友好报错
# ============================================================
# 使用说明：
#   pip install openai
#   在环境变量中设置：DEEPSEEK_API_KEY=你的key
# ============================================================

import os
import json
import time
import hashlib
from openai import (
    OpenAI,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    APIError,
)

# ── 模型常量，需要换模型时只改这一处 ──────────────────────────
MODEL_NAME      = "deepseek-chat"
BASE_URL        = "https://api.deepseek.com"
REQUEST_TIMEOUT = 60     # 请求超时（秒），在 client 上设置，所有请求生效
MAX_RETRY       = 3      # 最大重试次数
RETRY_WAIT      = 2      # 重试基础间隔秒数（限流时按 attempt 指数退避）
TEMPERATURE     = 0.2    # 总结类任务用低温度，保证结果稳定可复现
MAX_SECTION_LEN = 5000   # 单章节最大字符数
#   注：此处按"字符"截断，中文 1 字符 ≈ 1.5~2 token。DeepSeek-chat
#   上下文 64K，单章节远不会溢出，截断只影响成本/延迟，不会爆 context。
#   如需更精确控制成本，可后续引入 tiktoken 改为按 token 截断（非必须）。
MAP_MAX_TOKENS    = 512   # Map 阶段每章节小摘要，2~3 句话足够
REDUCE_MAX_TOKENS = 4096  # Reduce 阶段要吐结构化摘要 + 完整 mindmap，需放宽
CACHE_DIR         = "./cache"
# ─────────────────────────────────────────────────────────────


# ── client 单例：避免每次调用重复初始化 ──────────────────────
_client = None


def _get_client() -> OpenAI:
    cert_file = os.environ.get("SSL_CERT_FILE")
    if cert_file and not os.path.exists(cert_file):
        os.environ.pop("SSL_CERT_FILE", None)
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise Exception("DeepSeek API 调用失败：未找到环境变量 DEEPSEEK_API_KEY")
        # timeout 放在 client 上，作为所有请求的默认超时
        _client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=REQUEST_TIMEOUT)
    return _client


def _call_deepseek(
    prompt: str,
    use_json_mode: bool = False,
    max_tokens: int = 2048,
    temperature: float = TEMPERATURE,
) -> str:
    """
    基础封装：调用 DeepSeek API，返回纯文本响应（保证非空）。
    内置重试机制；限流走指数退避，鉴权失败立即抛错不重试。
    use_json_mode=True 时启用 DeepSeek 原生 JSON 模式。
    """
    client = _get_client()

    kwargs = {
        "model"      : MODEL_NAME,
        "messages"   : [{"role": "user", "content": prompt}],
        "max_tokens" : max_tokens,
        "temperature": temperature,
    }
    if use_json_mode:
        # 原生 JSON 模式（注意：prompt 中需出现 "json" 字样，下方 prompt 已满足）
        kwargs["response_format"] = {"type": "json_object"}

    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            # 空内容防护：内容过滤 / 服务异常时 content 可能为 None，
            # 若直接返回会让上游 json.loads(None) 抛 TypeError 绕过异常处理。
            if not content or not content.strip():
                last_err = "DeepSeek 返回空内容（可能触发内容过滤或服务异常）"
                if attempt < MAX_RETRY:
                    time.sleep(RETRY_WAIT)
                    continue
                break
            return content

        except AuthenticationError:
            # 鉴权失败重试无意义，立即抛错
            raise Exception("DeepSeek API 调用失败：API Key 无效，请检查 DEEPSEEK_API_KEY")

        except RateLimitError as e:
            # 限流是典型瞬时错误，做指数退避重试
            last_err = f"请求超出频率限制：{e}"
            if attempt < MAX_RETRY:
                time.sleep(RETRY_WAIT * attempt)
                continue

        except (APITimeoutError, APIConnectionError) as e:
            last_err = f"网络异常/超时：{e}"
            if attempt < MAX_RETRY:
                time.sleep(RETRY_WAIT)
                continue

        except APIError as e:
            # 其余 API 层错误（5xx 等）
            last_err = f"API 错误：{e}"
            if attempt < MAX_RETRY:
                time.sleep(RETRY_WAIT)
                continue

    raise Exception(f"DeepSeek API 调用失败（已重试 {MAX_RETRY} 次）：{last_err}")


def _safe_json_loads(text: str) -> dict:
    """
    防御性 JSON 解析：
      - 开了 JSON 模式后一般是合法 JSON，但仍兜底去 ``` 围栏
      - 解析失败时给出可读报错（最常见原因是 max_tokens 截断）
    """
    if not text or not text.strip():
        raise Exception("DeepSeek 返回内容为空，无法解析 JSON")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise Exception(
            f"JSON 解析失败（常见原因：max_tokens 截断导致 JSON 不完整）：{e}\n"
            f"原始内容前 200 字：{text[:200]}"
        )


# ── 缓存：相同正文 + 相同语言直接复用结果，联调时省 token/省时间 ──
def _cache_key(parsed_doc: dict, lang: str) -> str:
    raw = (parsed_doc.get("full_text", "") + "|" + lang).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _load_cache(key: str):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None  # 缓存损坏则当作未命中
    return None


def _save_cache(key: str, result: dict) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, f"{key}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 缓存写失败不影响主流程


def _map_section(section: dict, lang: str) -> str:
    """Map 阶段：对单个章节生成简短摘要。"""
    if lang == "zh":
        lang_instruction = "请用中文回答。"
        task = f"以下是论文章节「{section['title']}」的内容，请用2~3句话概括其核心要点："
    else:
        lang_instruction = "Please respond in English."
        task = f"Below is the content of section '{section['title']}'. Summarize its key points in 2-3 sentences:"

    prompt = (
        f"{lang_instruction}\n"
        f"{task}\n\n"
        f"{section['content'][:MAX_SECTION_LEN]}"
    )
    return _call_deepseek(prompt, max_tokens=MAP_MAX_TOKENS)


def _reduce_summaries(title: str, section_summaries: list, lang: str) -> dict:
    """
    Reduce 阶段：将所有章节摘要合并，生成最终结构化输出（JSON）。
    启用 JSON 模式 + 放宽 max_tokens，避免长论文输出被截断。
    """
    combined = "\n\n".join(
        f"[{i+1}] {s}" for i, s in enumerate(section_summaries)
    )

    if lang == "zh":
        prompt = (
            "请用中文回答所有字段值。\n"
            f"论文标题：{title}\n\n"
            f"以下是各章节摘要：\n{combined}\n\n"
            "请根据以上内容，输出如下 JSON 结构：\n"
            "{\n"
            '  "one_sentence": "一句话总结全文，50字以内",\n'
            '  "structured_summary": {\n'
            '    "problem": "研究了什么问题",\n'
            '    "method": "用了什么方法",\n'
            '    "result": "取得了什么结果",\n'
            '    "contribution": "主要贡献是什么"\n'
            '  },\n'
            '  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4"],\n'
            '  "mindmap_markdown": "# 论文标题\\n## 研究问题\\n- 要点\\n## 方法\\n- 要点\\n## 结果\\n- 要点\\n## 结论\\n- 要点"\n'
            "}\n"
            "注意：keywords 必须给出 3~5 个；problem/method/result/contribution 四个字段都必须填写。"
        )
    else:
        prompt = (
            "Please respond in English for all field values.\n"
            f"Paper title: {title}\n\n"
            f"Section summaries:\n{combined}\n\n"
            "Output the following JSON structure:\n"
            "{\n"
            '  "one_sentence": "One sentence summary within 30 words",\n'
            '  "structured_summary": {\n'
            '    "problem": "What problem was studied",\n'
            '    "method": "What method was used",\n'
            '    "result": "What results were achieved",\n'
            '    "contribution": "What is the main contribution"\n'
            '  },\n'
            '  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],\n'
            '  "mindmap_markdown": "# Paper Title\\n## Problem\\n- point\\n## Method\\n- point\\n## Results\\n- point\\n## Conclusion\\n- point"\n'
            "}\n"
            "Note: keywords must contain 3-5 items; all four fields "
            "problem/method/result/contribution must be filled."
        )

    raw = _call_deepseek(
        prompt,
        use_json_mode=True,
        max_tokens=REDUCE_MAX_TOKENS,
    )
    return _safe_json_loads(raw)


def summarize_paper(parsed_doc: dict, lang: str = "zh") -> dict:
    """
    调用 DeepSeek API，对解析后的论文生成结构化摘要与思维导图数据。

    Args:
        parsed_doc : parse_pdf() 的完整返回值，包含以下字段：
                     - title       : str，论文标题
                     - full_text   : str，论文全文
                     - sections    : list[dict]，每项格式为：
                                     {"title": str, "content": str}
                     - word_count  : int，全文字数
                     - parse_method: str，解析方式标识

        lang      : 输出语言，默认 "zh"（中文）。
                    传入 "en" 时所有文本字段均使用英文输出。

    Returns:
        dict，结构如下：
        {
            "one_sentence"       : str,
            "structured_summary" : {"problem": str, "method": str,
                                    "result": str, "contribution": str},
            "keywords"           : list[str],
            "mindmap_markdown"   : str,
            "model_used"         : str,
        }

    Raises:
        Exception : API Key 无效、网络超时、JSON 解析失败、无可用文本等情况时抛出
    """

    title     = parsed_doc.get("title", "未知论文")
    sections  = parsed_doc.get("sections", [])
    full_text = parsed_doc.get("full_text", "")

    # ── 缓存命中则直接返回 ────────────────────────────────────
    cache_key = _cache_key(parsed_doc, lang)
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    # 若无章节信息，降级为按 MAX_SECTION_LEN 切块的多个伪章节，
    # 避免只取 full_text 前 5000 字符而丢掉长论文后半部分。
    if not sections:
        if not full_text.strip():
            raise Exception("summarize_paper 失败：parsed_doc 既无 sections 也无 full_text")
        chunks = [
            full_text[i:i + MAX_SECTION_LEN]
            for i in range(0, len(full_text), MAX_SECTION_LEN)
        ]
        sections = [{"title": f"全文-{i+1}", "content": c} for i, c in enumerate(chunks)]

    # ── Map 阶段：逐章节摘要 ──────────────────────────────────
    section_summaries = []
    for section in sections:
        if not section.get("content", "").strip():
            continue
        section_summaries.append(_map_section(section, lang))

    if not section_summaries:
        raise Exception("summarize_paper 失败：parsed_doc 中没有可用的文本内容")

    # ── Reduce 阶段：合并生成结构化 JSON ─────────────────────
    result = _reduce_summaries(title, section_summaries, lang)

    # ── 字段级校验与兜底 ──────────────────────────────────────
    # structured_summary：逐字段补齐，避免模型漏 key 导致 1号位 KeyError
    ss = result.get("structured_summary") or {}
    if not isinstance(ss, dict):
        ss = {}
    structured = {k: ss.get(k, "") for k in ("problem", "method", "result", "contribution")}

    # keywords：保证是 list[str]，最多 5 个（下限 3 无法凭空补，仅在 prompt 中要求）
    keywords = result.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = [keywords]
    keywords = [str(k) for k in keywords if str(k).strip()][:5]

    # mindmap_markdown：兜底去围栏，符合"不加 ``` 包裹"的契约
    mindmap = result.get("mindmap_markdown", f"# {title}")
    if isinstance(mindmap, str):
        mindmap = mindmap.strip()
        if mindmap.startswith("```"):
            mindmap = mindmap.strip("`").strip()
            if mindmap.lower().startswith("markdown"):
                mindmap = mindmap[len("markdown"):].strip()
    else:
        mindmap = f"# {title}"

    final = {
        "one_sentence"       : result.get("one_sentence", ""),
        "structured_summary" : structured,
        "keywords"           : keywords,
        "mindmap_markdown"   : mindmap,
        "model_used"         : MODEL_NAME,
    }

    _save_cache(cache_key, final)
    return final
