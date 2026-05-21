# ============================================================
# 【2号位接口契约】search_contract.py
# 负责人：2号位（Agent 搜索 / 文献爬取）
# 集成方：1号位
# 版本：v1.0  冻结日期：待确认
# ============================================================
# 规则：
#   1. 函数名、参数名、返回字段名不可自行修改
#   2. 所有字段必须存在，无数据时填写默认值（见下方说明）
#   3. local_path 对应的 PDF 文件必须在本地真实存在
#   4. 网络异常、下载失败时抛出 Exception，附带可读的错误信息
#   5. 完成后删除下方 Mock 实现，替换为真实逻辑
# ============================================================


def search_papers(query: str, max_results: int = 5) -> list[dict]:
    """
    根据关键词搜索学术论文，并将 PDF 下载到本地。

    Args:
        query       : 搜索关键词，例如 "transformer attention mechanism"
        max_results : 最多返回论文数量，默认 5，建议不超过 10

    Returns:
        list[dict]，每个元素结构如下：

        {
            "title"      : str,        # 论文标题，不可为空
            "authors"    : list[str],  # 作者列表，无数据时填 []
            "year"       : int,        # 发表年份，无数据时填 0
            "abstract"   : str,        # 摘要原文，无数据时填 ""
            "pdf_url"    : str,        # PDF 原始链接，无数据时填 ""
            "local_path" : str,        # PDF 本地绝对路径，下载失败时填 ""
            "source"     : str,        # 来源平台，例如 "arxiv" / "semantic_scholar"
        }

    Raises:
        Exception: 当网络不可用或搜索 API 返回错误时抛出，
                   例如 raise Exception("arXiv API 请求失败：连接超时")

    Notes:
        - local_path 非空时，对应文件必须真实存在于磁盘
        - 建议将 PDF 统一下载至 ./downloads/ 目录
        - 单次调用总耗时建议控制在 30 秒以内
    """

    # ── Mock 实现（1号位占位用，2号位替换此处）──────────────
    import os
    os.makedirs("./downloads", exist_ok=True)

    return [
        {
            "title"      : "Attention Is All You Need",
            "authors"    : ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "year"       : 2017,
            "abstract"   : "We propose a new simple network architecture, the Transformer, "
                           "based solely on attention mechanisms, dispensing with recurrence "
                           "and convolutions entirely.",
            "pdf_url"    : "https://arxiv.org/pdf/1706.03762",
            "local_path" : "",   # Mock 不实际下载文件
            "source"     : "arxiv",
        },
        {
            "title"      : "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors"    : ["Jacob Devlin", "Ming-Wei Chang"],
            "year"       : 2019,
            "abstract"   : "We introduce BERT, which stands for Bidirectional Encoder "
                           "Representations from Transformers.",
            "pdf_url"    : "https://arxiv.org/pdf/1810.04805",
            "local_path" : "",
            "source"     : "arxiv",
        },
    ]
    # ── Mock 结束 ─────────────────────────────────────────────
