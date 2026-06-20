# 后续改进备忘录

> 汇总已讨论、尚未实施的改进方向。每项含「动机 / 方案 / 涉及文件 / 风险 / 验收」。
> 通用约束见文末。优先级：P0 先做，P3 按需。

## 优先级总览

| # | 改进 | 优先级 | 风险 | 主要收益 |
|---|------|--------|------|----------|
| 1 | 搜索精度（短语/降级/排序/去重） | **P0** | 低 | 搜得更准、不再空结果 |
| 2 | 检索增强：OpenAlex 选题 + Query Rewriter　✅ 可用 | P1 | 低 | 相关性选题、中文/自然语言检索 |
| 3 | LLM 摘要并发 | P1 | 中 | 缩短摘要阶段耗时 |
| 4 | MinerU 批处理 | P2 | 高 | 缩短冷启动（已被缓存摊销） |
| 5 | 零散项（见第 5 节） | P3 | 低 | 一致性 / 收尾 |

---

## 1. 搜索精度改进（P0，低风险，建议先做）

**现状**：`agents/search_agent.py` 把 query 按空格拆词，一律 `all:词 AND all:词`，无排序、无去重。又严又糙。

### 1.1 短语精确化
- 动机：`in-context learning` 被拆成两个词 AND，丢了短语语义。
- 方案：词组用引号做精确短语，如 `all:"in-context learning"`；或整串先按短语搜、再退化到分词。
- 涉及：`search_agent.py` 查询构造。

### 1.2 0 结果自动降级
- 动机：多词强制 `AND`（如 `diffusion model image generation`）易召回 0。
- 方案：严格 AND 搜不到时，自动降级为 `OR` 或去掉次要词重试，杜绝空结果。
- 涉及：`search_agent.py`（在 `_fetch_arxiv` 外再包一层"降级重试"）。

### 1.3 sortBy 排序选项
- 动机：URL 无 `sortBy`，只能吃默认；展示时想要「最相关」或「最新」。
- 方案：URL 加 `sortBy=relevance|submittedDate` + `sortOrder`；侧栏给开关。
- 涉及：`search_agent.py`（加参数，注意不破契约——可加可选参数或读环境变量）、`app.py`（侧栏 UI）。

### 1.4 版本去重
- 动机：同一论文 v1/v2 可能都返回。
- 方案：按 arxiv_id 主体（去掉 `vN`）去重，保留最新版本。
- 涉及：`search_agent.py` 的 `_parse_entries`。

### （附带）字段加权 / 中文检测
- 字段加权：优先 `ti:`+`abs:` 命中，相关性更高。
- 中文检测：query 含中文时给出提示（arXiv 是英文库，中文几乎搜不到），进阶可自动英译。

**验收**：`in-context learning` 等短语搜得准；`diffusion model image generation` 不再 0 结果；排序开关生效；结果无重复版本。**不破 `search_contract` 契约**。

---

## 2. 检索增强：OpenAlex 选题 + Query Rewriter（P1）　✅ 可用

**动机**：arXiv 是关键词匹配、无质量排序。用 OpenAlex 做选题（带**引用数**、跨库），再前置一层 Query Rewriter 把用户自然语言（可中文）改写成英文检索词，顺带解决「中文搜不到英文库」。

> **为什么是 OpenAlex 而非 Semantic Scholar**：最初按 S2 实现（`semantic_agent.py` 仍在，作可选后备），但 **S2 的 API key 申请被拒**（开放资源有限），且无 key 实测持续 429。改用 **OpenAlex**——免费、**无需审批 key**、限流宽（polite pool 约 10 万/天），功能对等。

**pipeline**：`自然语言 → Query Rewriter(LLM) → OpenAlex 智能选题(相关性优先) → arXiv 取 PDF → 解析 → 摘要`

### ✅ 已实现并实测（2026-06）
- `agents/query_rewriter.py`：自然语言→英文检索词，复用 DeepSeek，失败兜底返回原文。实测 `我想了解大模型如何减少幻觉` → `large language model hallucination reduction`。
- `agents/openalex_agent.py`：OpenAlex Works API，含 **polite pool(mailto) / 重试 / 429 退避 / 限速 / 缓存（前缀 search_oa_）**；重建倒排 abstract、正则提取 arXiv id。排序**默认相关性**（可选 `OPENALEX_SORT=citations` 找高引；实测纯引用在宽泛词下会顶弱相关高引如 R 语言，故默认相关性）。**实测免 key 直接返回**，PDF 衔接正常。
- `agents/semantic_agent.py`：S2 版（保留为可选后备，需 key）。
- `agents/search_agent.py`：容错 import + 来源优先级 `OpenAlex > S2 > arXiv`，缓存按来源区分，**契约字段不变（app/UI 不用动）**。

### 关键约束
强依赖 PDF（检索→下载→MinerU→摘要）。选题源很多论文无 arXiv 全文 → **有 arXiv id 走 arXiv 下载，否则用 open-access 链接，再不行 `local_path` 留空、`safe_parse` 用 abstract 兜底**。

### 启用步骤（环境变量；默认全关 = 纯 arXiv）
```bash
USE_QUERY_REWRITE=1                 # 开「自然语言→英文检索词」
USE_OPENALEX=1                      # 开 OpenAlex 检索（推荐）
OPENALEX_MAILTO=你的邮箱            # 进 polite pool，更稳更快（强烈建议）
# 可选 OPENALEX_SORT=citations      # 找经典高引（宽泛词慎用，会顶弱相关高引）
# 可选后备：USE_SEMANTIC=1 + S2_API_KEY=...（拿到 S2 key 时才用）
```

### 剩余 TODO（组员）
- 设 `OPENALEX_MAILTO`（进 polite pool）。
- `openalex_agent.py` 排序/字段精调（目前按引用数；可加相关性加权、年份/领域过滤）。
- 可选：`citation_count` 透传到 UI 展示（`search_contract` 可加可选字段）。

**验收**：开 `USE_QUERY_REWRITE` + `USE_OPENALEX` 后，中文自然语言进 → OpenAlex 按引用排序选题 → 有 arXiv 版正常解析 → 无 PDF 的退化到摘要；关掉开关回到纯 arXiv。

---

## 3. LLM 摘要并发（P1，提速）

**动机**：`llm_agent.py` 的 Map 阶段逐章节串行调 DeepSeek，多篇/多章节时累加耗时。

**方案**：Map 阶段章节级并发（线程池 / 异步），多篇论文也可并发；注意 DeepSeek 限流，控制并发数 + 复用已有重试。

**涉及**：`agents/llm_agent.py`（`summarize_paper` 的 Map 循环）、可选 `app.py`（多篇并发编排）。

**验收**：多章节论文摘要耗时明显下降；不触发 429；结果与串行一致（temperature 已固定 0.2）。

---

## 4. MinerU 批处理（P2，高风险，收益主要在冷启动）

**动机**：`pdf_parser.py` 现在逐篇 `subprocess` 调 `mineru` CLI，**每篇都重新加载模型**（冷启动大头），串行 N 篇 = N 次模型加载；单篇仅占 ~1G 显存，GPU 算力大量闲置。

**方案**（两条，风险递增）：
- **A（较稳）批量解析**：把多篇 PDF 放一个临时目录，**一次 `mineru -p <dir> -o <out>`**，模型只加载一次，再按文件名分别取各自的 md。改造 `pdf_parser` 增加一个"批量"入口，app 层把同一批论文聚合调用。
- **B（高风险）常驻服务 + 并发**：起常驻 mineru API 服务，HTTP 多并发喂满 GPU。需研究 pipeline 后端的并发安全性。

**注意**：冷启动已被三层缓存摊销（热跑 0.4s），**此项主要改善"第一次跑"**。课程范围内性价比不高，**建议单独开分支研究**，别动主分支。

**涉及**：`agents/pdf_parser.py`（批量入口，保持 `parse_pdf` 单篇契约不变）、`app.py`（解析阶段编排）。

**验收**：3 篇冷启动总耗时较现状明显下降（来自"模型只加载一次"）；单篇 `parse_pdf` 行为与缓存不受影响。

---

## 5. 零散待办（P3）

- **`pdf_parser.py` 后处理（曾尝试的 v1.4，有 bug，需重做）**：表格 HTML 清理、References/Appendix 尾部截断。重做时务必修两处根因：
  1. `_normalize_title` 的编号正则**要求分隔符**（`^(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])[.)]\s+`），并去掉 `IGNORECASE`，否则会吃掉 `Model`/`Limitations` 等正文标题首字母。
  2. `_is_noise` **别用"开头匹配 + 非字母"**（会误杀 `Prompt Design`/`Reference-based` 等正文章节，对本 LLM/RAG 领域尤其危险），改为整标题精确匹配；并从噪音词里移除 `prompt/prompts/limitations`。
  3. 过滤后若 `sections` 为空，回退原始列表，别整篇砍光。
- **检索缓存 TTL**：当前默认永不过期（demo 友好但搜不到新论文）。可视需要设 `ARXIV_SEARCH_CACHE_TTL`，或在 UI 加"强制刷新"。
- **缓存 key 粒度**：检索缓存按 `(query, max_results)`，篇数不同就 miss；可改为缓存较大结果集再取前 N。
- **去名一致性**：`agents/pdf_parser.py` 注释仍有真名；如要统一去名，按 `search_agent.py` 改成位号。
- **PDF 内嵌**：单视图「原始 PDF」嵌的是远程 arXiv URL，可改为优先加载本地已下载的 PDF（更稳、离线可用）。

---

## 通用约束（所有改动都遵守）

- **不改 `contracts/` 的函数名 / 参数名 / 返回字段名**；要加参数用"可选参数 + 默认值"或环境变量。
- **复用已有的重试 / 退避 / 缓存** 机制，新数据源同样要做缓存。
- **高风险项（MinerU 批处理、S2 接入）开新分支**，主分支始终保留可运行的稳定版。
- 改完**实测**：尤其搜索类改动，验证"短语更准 / 不空结果 / 排序生效 / 不触发 429"。
