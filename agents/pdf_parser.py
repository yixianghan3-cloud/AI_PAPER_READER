# ============================================================
# 【3号位接口契约】pdf_parser.py
# 负责人：郭瑞超（PDF 解析 / 文档结构化）
# 集成方：1号位
# 版本：v1.3（1号位集成修订版）
# ============================================================
# v1.3 相对 v1.2 的修订（针对本机 RTX 5060 / CUDA 13.2 环境）：
#   1. 【backend 固定】显式指定 -b pipeline。
#      原因：默认 backend 在 MinerU 3.x 为 hybrid-auto-engine，会走
#      lmdeploy/turbomind，而 turbomind 预编译轮子与本机 CUDA 13 不兼容
#      （ImportError: DLL load failed while importing _turbomind）。
#      pipeline 不依赖 turbomind，且 torch 为 cu130 时其 OCR 仍走 GPU，
#      是本机（Blackwell sm_120）唯一稳定可用的后端。
#   2. 【环境注入】子进程注入经本机 README 验证过的 MinerU 环境：
#        - pop SSL_CERT_FILE：系统里该变量指向不存在的 cacert.pem，
#          会让 httpx 在 ssl.create_default_context 启动即崩。
#        - MINERU_MODEL_SOURCE=modelscope：国内源，避免模型下载失败。
#        - MODELSCOPE_CACHE / CUDA_PATH：见文件顶部常量（机器相关，换机器需改）。
#   3. 【可观测】MinerU 报错信息从 stderr[:500] 放宽到 [:2000]，
#      避免 traceback 末尾真正的 XxxError 被截断。
# ------------------------------------------------------------
# v1.2 相对 v1.1 的修订：
#   1. 【致命修复】MinerU 输出路径检测：MinerU 会在输出目录下生成
#      {basename}/{method}/{basename}.md 的嵌套结构，原代码只在顶层
#      查找，导致 100% 找不到文件、解析永远失败。改为递归查找 .md。
#   2. 清理 markdown 中失效的图片链接（MinerU 图片随临时目录删除，
#      链接会指向已删除的路径，UI 直接渲染会显示破图）。
#   3. 超时时长可通过环境变量调整，方便 demo：MINERU_TIMEOUT（秒，默认 300）
# ------------------------------------------------------------
# 契约约束（保持不变，不可修改）：
#   - 函数名 parse_pdf、参数 local_path、返回字段名均不可改
#   - sections 为 list[dict]，每项含 "title" 和 "content"
#   - full_text 不可为空
#   - 文件不存在抛 FileNotFoundError，解析失败抛 Exception
# ============================================================

import os
import re
import glob
import subprocess
import tempfile

# ─────────────────────────────────────────────────────────────
# 机器相关配置（换机器 / 换队友环境时，主要改这一段）
# 默认值取自本机（RTX 5060 + CUDA 13.2）README 中验证过的配置。
# 这些也可由外部环境变量覆盖：若启动 Streamlit 的终端已 export 了
# 对应变量，则优先用外部值，不会被下方默认值覆盖。
# ─────────────────────────────────────────────────────────────
# 解析后端：本机固定 pipeline（兼容性最强，详见文件头 v1.3 说明）
MINERU_BACKEND = os.environ.get("MINERU_BACKEND", "pipeline")

# 模型下载源：modelscope 为国内源，提速且更稳
MINERU_MODEL_SOURCE = os.environ.get("MINERU_MODEL_SOURCE", "modelscope")

# 模型缓存目录：定向到 D 盘，防止 C 盘爆满（机器相关路径）
MODELSCOPE_CACHE = os.environ.get("MODELSCOPE_CACHE", "D:/MinerU_Models")

# CUDA 工具包路径：MinerU 找不到 CUDA_PATH 时会 AssertionError（机器相关路径）
CUDA_PATH = os.environ.get(
    "CUDA_PATH", "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.2"
)

# 单次解析超时（秒）。pipeline 纯靠本机算力，公式多的长 PDF 可能较慢，
# demo 时可调小或依赖缓存。274 页公式 PDF 约 10~15 分钟，论文一般 1~3 分钟。
MINERU_TIMEOUT = int(os.environ.get("MINERU_TIMEOUT", "300"))

# md 落盘缓存：默认开启。缓存文件与 PDF 同目录同名（如 downloads/1706.03762.md）。
# 命中缓存可跳过 MinerU，秒级返回，适合反复测试与 demo。
# 设 MINERU_CACHE=0 可关闭，强制每次重新解析。
MINERU_CACHE = os.environ.get("MINERU_CACHE", "1") != "0"


def parse_pdf(local_path: str) -> dict:
    """
    解析本地 PDF 文件，提取结构化文本内容（基于 MinerU pipeline 后端）。

    Args:
        local_path : PDF 文件的本地绝对路径，
                     来自 search_papers() 返回值中的 local_path 字段

    Returns:
        dict，结构如下：
        {
            "title"      : str,         # 从 PDF 提取的标题，无法识别时填 ""
            "full_text"  : str,         # 完整正文（Markdown 格式），不可为空
            "sections"   : list[dict],  # [{"title": str, "content": str}, ...]
            "word_count" : int,         # full_text 的近似字数
            "parse_method": str,        # "mineru"（实跑）或 "mineru-cache"（命中缓存）
        }

    Raises:
        FileNotFoundError : 当 local_path 指向的文件不存在时抛出
        Exception         : 当 MinerU 未安装、超时、或解析失败时抛出，附可读信息
    """
    # 1. 文件不存在 → FileNotFoundError（契约要求，必须原样透传，不可包成 Exception）
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"PDF 文件不存在：{local_path}")

    # 2. 先查 md 落盘缓存；命中则跳过 MinerU，未命中才跑 MinerU 并写缓存
    raw_md = _read_cache(local_path)
    if raw_md:
        parse_method = "mineru-cache"
    else:
        raw_md = _run_mineru(local_path, timeout=MINERU_TIMEOUT)
        _write_cache(local_path, raw_md)   # 尽力而为，写失败不影响解析
        parse_method = "mineru"

    # 3. 清理 markdown（去掉失效图片链接、压缩多余空行）
    full_text = _clean_markdown(raw_md)
    if not full_text.strip():
        raise Exception("PDF 解析失败：清理后正文为空")

    # 4. 提取标题 + 拆分章节
    title, sections = _split_sections(full_text)

    # 5. 计算字数
    word_count = _count_words(full_text)

    return {
        "title": title,
        "full_text": full_text,
        "sections": sections,
        "word_count": word_count,
        "parse_method": parse_method,
    }


# ─────────────────────────────────────────────────────────────
# md 落盘缓存
# ─────────────────────────────────────────────────────────────
def _cache_path(local_path: str) -> str:
    """缓存 md 路径：与 PDF 同目录、同名、.md 后缀。"""
    return os.path.splitext(local_path)[0] + ".md"


def _read_cache(local_path: str) -> str:
    """读取有效缓存的 MinerU 原始 md；无有效缓存返回 ""。"""
    if not MINERU_CACHE:
        return ""
    cache = _cache_path(local_path)
    if not os.path.exists(cache):
        return ""
    # 若 PDF 比缓存还新（被重新下载过），缓存视为失效
    try:
        if os.path.getmtime(local_path) > os.path.getmtime(cache):
            return ""
    except OSError:
        pass
    try:
        with open(cache, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()   # 空内容会被当作未命中，触发重新解析
    except OSError:
        return ""


def _write_cache(local_path: str, text: str) -> None:
    """把 MinerU 原始 md 写入缓存（尽力而为，写失败不抛异常）。"""
    if not MINERU_CACHE:
        return
    try:
        with open(_cache_path(local_path), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass   # 缓存只是优化，写不进去也不影响主流程


# ─────────────────────────────────────────────────────────────
# MinerU 环境
# ─────────────────────────────────────────────────────────────
def _build_mineru_env() -> dict:
    """
    构造 MinerU 子进程的环境变量。

    Streamlit 是独立进程，subprocess 继承的是"启动 Streamlit 那个终端"
    的环境，而非用户手动 export 的终端。因此这里把本机验证过的 MinerU
    环境直接注入子进程环境副本，确保不论从哪个终端启动都能跑通。
    （仅修改子进程的环境副本，不影响当前进程与系统环境。）
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # 坏的证书路径会让 httpx 在 ssl.create_default_context 启动即崩，
    # 这里从子进程环境副本里移除它（pop 不存在也不报错）。
    env.pop("SSL_CERT_FILE", None)

    # 模型下载源 / 缓存目录 / CUDA 路径（详见文件顶部常量）
    env["MINERU_MODEL_SOURCE"] = MINERU_MODEL_SOURCE
    env["MODELSCOPE_CACHE"]    = MODELSCOPE_CACHE
    # CUDA_PATH：若外部已正确设置则不覆盖，避免在非本机环境写死错误路径
    if not env.get("CUDA_PATH"):
        env["CUDA_PATH"] = CUDA_PATH

    return env


# ─────────────────────────────────────────────────────────────
# MinerU 解析
# ─────────────────────────────────────────────────────────────
def _run_mineru(local_path: str, timeout: int = 300) -> str:
    """调用本地 mineru CLI 解析，返回 markdown 全文。失败时抛 Exception。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 固定 pipeline 后端（本机唯一稳定可用，详见文件头 v1.3 说明）
        cmd = [
            "mineru",
            "-p", local_path,
            "-o", tmpdir,
            "-m", "auto",
            "-b", MINERU_BACKEND,
        ]

        env = _build_mineru_env()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",   # Windows 下 stderr 可能非 utf-8，避免崩在解码上
                env=env,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise Exception("未找到 mineru 命令，请确认已安装 MinerU（pip install mineru）")
        except subprocess.TimeoutExpired:
            raise Exception(f"PDF 解析失败：MinerU 执行超时（超过 {timeout} 秒）")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            # 放宽到 2000，避免 traceback 末尾真正的 XxxError 被截断
            raise Exception(f"PDF 解析失败：MinerU 退出码非 0：{stderr[:2000]}")

        # 【关键修复】MinerU 输出是嵌套的：{tmpdir}/{basename}/{method}/{basename}.md
        # 原代码只在 tmpdir 顶层找，永远命中不到。改为递归查找全部 .md。
        md_files = glob.glob(os.path.join(tmpdir, "**", "*.md"), recursive=True)
        if not md_files:
            raise Exception(f"PDF 解析失败：MinerU 未生成 .md 文件，输出目录内容：{os.listdir(tmpdir)}")

        # 若有多个 .md，取体积最大的（一般是正文，其它可能是空壳或子文件）
        md_file = max(md_files, key=os.path.getsize)
        with open(md_file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()

        if not text:
            raise Exception("PDF 解析失败：MinerU 生成的 .md 为空")
        return text


# ─────────────────────────────────────────────────────────────
# 后处理
# ─────────────────────────────────────────────────────────────
def _clean_markdown(text: str) -> str:
    """清理 markdown：去掉失效图片链接、压缩连续空行。"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)   # 图片随临时目录删除，链接已失效
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_sections(full_text: str):
    """从 markdown 提取标题，并按 ## ~ ###### 切分章节。返回 (title, sections)。"""
    # 标题：优先取第一个一级标题 "# xxx"；没有则取首个非空行
    title = ""
    m = re.search(r"^#\s+(.+?)\s*$", full_text, re.MULTILINE)
    if m:
        title = m.group(1).strip()
    else:
        for line in full_text.split("\n"):
            if line.strip():
                title = line.strip().lstrip("# ").strip()
                break

    sections = []
    current_title = None
    current_content = []

    for line in full_text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r"^#{2,6}\s+\S", s):                 # 二~六级标题 → 新章节
            if current_title is not None:
                sections.append({
                    "title": current_title,
                    "content": " ".join(current_content).strip(),
                })
            current_title = re.sub(r"^#{2,6}\s+", "", s).strip()
            current_content = []
        elif re.match(r"^#\s+\S", s):                    # 一级标题（论文标题），跳过
            continue
        else:                                            # 正文
            if current_title is None:
                current_title = "正文"
            current_content.append(s)

    if current_title is not None:
        sections.append({
            "title": current_title,
            "content": " ".join(current_content).strip(),
        })

    if not sections:                                     # 一个标题都没识别出来 → 整篇兜底
        sections = [{"title": "正文", "content": full_text.strip()}]

    return title, sections


def _count_words(text: str) -> int:
    """近似字数：中文按字符数，英文/数字按词组数。"""
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[a-zA-Z0-9]+", text))
    return chinese + english


# ─────────────────────────────────────────────────────────────
# 命令行自测：python pdf_parser.py <pdf路径>
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python pdf_parser.py <pdf路径>")
        print("可选环境变量: MINERU_TIMEOUT=300  MINERU_BACKEND=pipeline")
        sys.exit(1)

    result = parse_pdf(sys.argv[1])
    print(f"标题      : {result['title']}")
    print(f"解析方式  : {result['parse_method']}")
    print(f"字数      : {result['word_count']}")
    print(f"章节数    : {len(result['sections'])}")
    for i, sec in enumerate(result["sections"], 1):
        preview = sec["content"][:60].replace("\n", " ")
        print(f"  [{i}] {sec['title']}  ({len(sec['content'])} 字)  {preview}...")
    print("\n--- full_text 前 500 字 ---")
    print(result["full_text"][:500])