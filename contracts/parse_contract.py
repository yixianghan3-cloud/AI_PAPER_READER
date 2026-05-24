# ============================================================
# 【3号位接口契约】parse_contract.py
# 负责人：3号位（PDF 解析 / 文档结构化）
# 集成方：1号位
# 版本：v1.1  冻结日期：待确认
# ============================================================
# 变更记录：
#   v1.1 - sections 字段由 dict 改为 list[dict]
#          格式：[{"title": str, "content": str}, ...]
#          原因：与 llm_contract v1.1 对齐，支持 Map-Reduce 遍历
# ============================================================
# 规则：
#   1. 函数名、参数名、返回字段名不可自行修改
#   2. sections 必须是 list[dict]，每项包含 "title" 和 "content" 两个 key
#   3. full_text 必须有实际文字内容，不可为空字符串
#   4. 文件不存在或解析彻底失败时抛出对应 Exception
#   5. 完成后删除下方 Mock 实现，替换为真实逻辑
# ============================================================


def parse_pdf(local_path: str) -> dict:
    """
    解析本地 PDF 文件，提取结构化文本内容。

    Args:
        local_path : PDF 文件的本地绝对路径，
                     来自 search_papers() 返回值中的 local_path 字段

    Returns:
        dict，结构如下：

        {
            "title"      : str,         # 从 PDF 提取的标题，无法识别时填 ""
            "full_text"  : str,         # 完整正文（Markdown 格式），不可为空
            "sections"   : list[dict],  # 章节列表，每项格式为：
                                        # {
                                        #     "title"   : str,  # 章节标题，如 "Introduction"
                                        #     "content" : str,  # 章节正文，无内容时填 ""
                                        # }
                                        # 示例：
                                        # [
                                        #   {"title": "Abstract",      "content": "We propose..."},
                                        #   {"title": "Introduction",  "content": "Recent work..."},
                                        #   {"title": "Method",        "content": "Our model..."},
                                        #   {"title": "Conclusion",    "content": "In this work..."},
                                        # ]
            "word_count"   : int,       # full_text 的近似字数（按空格分词即可）
            "parse_method" : str,       # 实际使用的解析方法，如 "pymupdf" / "mineru"
        }

    Raises:
        FileNotFoundError : 当 local_path 指向的文件不存在时抛出
        Exception         : 当 PDF 损坏或解析完全失败时抛出，附带可读错误信息

    Notes:
        - sections 的章节数量不固定，识别出几个就返回几个，不强制要求四个固定章节
        - sections 顺序应与论文原文顺序一致
        - full_text 使用 Markdown 格式，章节标题用 ## 表示
        - 页眉、页脚、页码请尽量清除
        - word_count 为英文单词数或中文字符数，大致准确即可
    """

    # ── Mock 实现（1号位占位用，3号位替换此处）──────────────
    import os
    if local_path and not os.path.exists(local_path):
        raise FileNotFoundError(f"PDF 文件不存在：{local_path}")

    mock_sections = [
        {
            "title"   : "Abstract",
            "content" : (
                "We propose a new simple network architecture, the Transformer, "
                "based solely on attention mechanisms."
            ),
        },
        {
            "title"   : "Introduction",
            "content" : (
                "Recurrent neural networks, long short-term memory and gated recurrent "
                "neural networks in particular, have been firmly established as state of "
                "the art approaches in sequence modeling and transduction problems."
            ),
        },
        {
            "title"   : "Method",
            "content" : (
                "The Transformer follows an encoder-decoder structure using stacked "
                "self-attention and point-wise, fully connected layers for both the "
                "encoder and decoder."
            ),
        },
        {
            "title"   : "Conclusion",
            "content" : (
                "In this work, we presented the Transformer, the first sequence "
                "transduction model based entirely on attention."
            ),
        },
    ]

    mock_full = "\n\n".join(
        f"## {sec['title']}\n\n{sec['content']}"
        for sec in mock_sections
    )

    return {
        "title"        : "Attention Is All You Need",
        "full_text"    : mock_full,
        "sections"     : mock_sections,
        "word_count"   : len(mock_full.split()),
        "parse_method" : "mock",
    }
    # ── Mock 结束 ─────────────────────────────────────────────
