# ============================================================
# 【4号位接口契约】llm_contract.py
# 负责人：4号位（大模型 Prompt / DeepSeek 对接）
# 集成方：1号位
# 版本：v1.1  冻结日期：待确认
# ============================================================
# 集成方式（1号位）：
#   USE_MOCK = False → 引用 agents/llm_agent.py 的真实实现（DeepSeek）
#   USE_MOCK = True  → 用下方 Mock 假数据
# 提示：真实实现需在环境变量中设置 DEEPSEEK_API_KEY，并 pip install openai。
# ============================================================
# 规则：
#   1. 函数名、参数名、返回字段名不可自行修改
#   2. 输入 parsed_doc 即 parse_pdf() 的完整返回值，不要假设字段缺失
#   3. mindmap_markdown 必须是合法的 Markdown 层级结构，不加 ``` 包裹
#   4. keywords 必须是 list[str]，长度 3~5 个
#   5. API 调用失败时抛出 Exception，附带可读的错误信息
# ============================================================

USE_MOCK = False   # demo 兜底 / 无 API Key 时改 True

if not USE_MOCK:
    # 真实实现：4号位的 agents/llm_agent.py（DeepSeek + Map-Reduce）
    from agents.llm_agent import summarize_paper   # noqa: F401

else:
    def summarize_paper(parsed_doc: dict, lang: str = "zh") -> dict:
        """
        调用 DeepSeek API，对解析后的论文生成结构化摘要与思维导图数据。

        Args:
            parsed_doc : parse_pdf() 的完整返回值，包含以下字段：
                         - title       : str，论文标题
                         - full_text   : str，论文全文
                         - sections    : list[dict]，每项格式为：
                                         {"title": str, "content": str}
                                         例如 [{"title": "Introduction", "content": "..."}]
                         - word_count  : int，全文字数
                         - parse_method: str，解析方式标识

            lang      : 输出语言，默认 "zh"（中文）。
                        传入 "en" 时，所有文本字段（one_sentence、structured_summary、
                        keywords、mindmap_markdown）均使用英文输出。
                        中文论文建议传 "zh"，英文论文建议传 "en"。

        Returns:
            dict，结构如下：

            {
                "one_sentence" : str,   # 一句话总结全文
                                        # 中文（lang="zh"）：50字以内
                                        # 英文（lang="en"）：30词以内
                "structured_summary" : {
                    "problem"      : str,  # 研究了什么问题
                    "method"       : str,  # 用了什么方法
                    "result"       : str,  # 取得了什么结果
                    "contribution" : str,  # 主要贡献是什么
                },
                "keywords"          : list[str],  # 3~5 个关键词，字符串列表
                "mindmap_markdown"  : str,         # Markmap 可直接渲染的 Markdown 文本
                "model_used"        : str,         # 实际使用的模型名，如 "deepseek-chat"
            }

        Raises:
            Exception : API Key 无效、余额不足、请求超时等情况时抛出，
                        例如 raise Exception("DeepSeek API 调用失败：rate limit exceeded")

        Notes:
            - mindmap_markdown 格式示例（直接可用，无需代码块包裹）：
                # 论文标题
                ## 研究问题
                - 核心问题描述
                ## 方法
                - 方法A
                - 方法B
                ## 实验结果
                - 指标提升 XX%
                ## 结论
                - 主要贡献

            - 长文本处理建议采用 Map-Reduce：
                1. 遍历 parsed_doc["sections"]，逐章节调用 LLM 生成小摘要
                2. 将所有小摘要拼接后，再次调用 LLM 合并为最终结构化输出
            - 单次调用建议设置 timeout=60 秒
            - lang 参数不影响返回字段名（字段名始终为英文），仅影响字段值的语言
        """

        # ── Mock 实现（1号位占位用，4号位替换此处）──────────────
        title = parsed_doc.get("title", "未知论文")

        mock_mindmap = (
            f"# {title}\n"
            "## 研究问题\n"
            "- 序列转换任务中 RNN/CNN 的计算瓶颈\n"
            "- 长距离依赖建模困难\n"
            "## 方法\n"
            "- 纯注意力机制架构（Transformer）\n"
            "- 多头自注意力（Multi-Head Attention）\n"
            "- 位置编码（Positional Encoding）\n"
            "## 实验结果\n"
            "- WMT 2014 英德翻译 BLEU 28.4（超越此前最优）\n"
            "- 训练时间大幅缩短\n"
            "## 结论\n"
            "- Transformer 成为序列建模主流架构\n"
            "- 为 BERT、GPT 等后续工作奠定基础"
        )

        return {
            "one_sentence" : "Transformer 提出了纯注意力机制的序列转换架构，在机器翻译任务上达到最优效果。",
            "structured_summary" : {
                "problem"      : "传统 RNN/CNN 在长序列建模中存在计算效率低、长距离依赖难以捕捉的问题。",
                "method"       : "提出 Transformer 架构，完全基于多头自注意力机制，摒弃循环与卷积结构。",
                "result"       : "在 WMT 2014 英德翻译任务上取得 BLEU 28.4 的最优成绩，训练时间显著减少。",
                "contribution" : "首次验证纯注意力机制可独立完成序列转换任务，开创了预训练语言模型时代。",
            },
            "keywords"         : ["Transformer", "注意力机制", "序列建模", "机器翻译", "自然语言处理"],
            "mindmap_markdown" : mock_mindmap,
            "model_used"       : "mock",
        }
        # ── Mock 结束 ─────────────────────────────────────────────