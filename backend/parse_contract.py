# ============================================================
# 【3号位接口契约】parse_contract.py
# 负责人：3号位（PDF 解析 / 文档结构化）
# 集成方：1号位
# 版本：v1.0  冻结日期：待确认
# ============================================================
# 规则：
#   1. 函数名、参数名、返回字段名不可自行修改
#   2. sections 下的四个子字段必须全部存在，无法识别时填 ""
#   3. full_text 必须有实际文字内容，不可为空字符串
#   4. 文件不存在或解析彻底失败时抛出 Exception
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
            "title"      : str,   # 从 PDF 中提取的标题，无法识别时填 ""
            "full_text"  : str,   # 完整正文（Markdown 格式），不可为空
            "sections"   : {
                "abstract"     : str,  # 摘要段落，无法识别时填 ""
                "introduction" : str,  # 引言段落，无法识别时填 ""
                "method"       : str,  # 方法段落，无法识别时填 ""
                "conclusion"   : str,  # 结论段落，无法识别时填 ""
            },
            "word_count"   : int,  # full_text 的近似字数（按空格分词即可）
            "parse_method" : str,  # 实际使用的解析方法，如 "pymupdf" / "mineru"
        }

    Raises:
        FileNotFoundError : 当 local_path 指向的文件不存在时抛出
        Exception         : 当 PDF 损坏或解析完全失败时抛出，附带可读错误信息

    Notes:
        - full_text 使用 Markdown 格式，章节标题用 ## 表示
        - 页眉、页脚、页码请尽量清除
        - word_count 为英文单词数或中文字符数，大致准确即可
    """

    # ── Mock 实现（1号位占位用，3号位替换此处）──────────────
    import os
    if local_path and not os.path.exists(local_path):
        raise FileNotFoundError(f"PDF 文件不存在：{local_path}")

    mock_abstract = (
        "We propose a new simple network architecture, the Transformer, "
        "based solely on attention mechanisms."
    )
    mock_intro = (
        "Recurrent neural networks, long short-term memory and gated recurrent "
        "neural networks in particular, have been firmly established as state of "
        "the art approaches in sequence modeling and transduction problems."
    )
    mock_method = (
        "## Model Architecture\n\n"
        "The Transformer follows an encoder-decoder structure using stacked "
        "self-attention and point-wise, fully connected layers for both the "
        "encoder and decoder."
    )
    mock_conclusion = (
        "In this work, we presented the Transformer, the first sequence "
        "transduction model based entirely on attention."
    )
    mock_full = (
        f"## Abstract\n\n{mock_abstract}\n\n"
        f"## Introduction\n\n{mock_intro}\n\n"
        f"{mock_method}\n\n"
        f"## Conclusion\n\n{mock_conclusion}"
    )

    return {
        "title"      : "Attention Is All You Need",
        "full_text"  : mock_full,
        "sections"   : {
            "abstract"     : mock_abstract,
            "introduction" : mock_intro,
            "method"       : mock_method,
            "conclusion"   : mock_conclusion,
        },
        "word_count"   : len(mock_full.split()),
        "parse_method" : "mock",
    }
    # ── Mock 结束 ─────────────────────────────────────────────
