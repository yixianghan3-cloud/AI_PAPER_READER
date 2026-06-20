# AI Paper Reader · 学术论文智能摘要系统

> 自然语言/关键词/论文标题检索 → PDF 解析 → LLM 摘要 → 思维导图，一站式论文速读工具。
> 技术栈：Streamlit + OpenAlex / arXiv API + MinerU + DeepSeek。

本文档既是**组员上手指南**，也是**踩坑备忘录**。环境搭建部分务必逐条照做，
本项目在环境配置上有几个非常隐蔽的坑（SSL、CUDA、网络），不照做大概率跑不起来。

---

## 🚀 组员请先看这里（远程访问，免搭环境）

**只是想用这个工具看论文 / 看 demo 效果？不用装 Python、不用配环境、不用 GPU 和 API Key。**

👉 **请优先阅读 [REMOTE_ACCESS.md](REMOTE_ACCESS.md)** —— 装一个 Tailscale 客户端，3 步即可远程访问跑在主机上的 demo。

> 真正吃环境的活（MinerU 解析、DeepSeek 摘要）都在主机那台跑，你这边只是开个网页。
> 只有当你需要**本地自己跑、参与改代码**时，才往下看下面的「环境搭建」部分（坑较多，做好心理准备）。

---

## 一、项目是做什么的

输入**关键词、中文研究方向、或论文标题**（如 `transformer`、`我想了解大模型如何减少幻觉`、
`Attention Is All You Need`），系统自动：

1. **查询改写**（可选）：自然语言/中文 → 英文检索词（DeepSeek；纯英文关键词或精确标题原样保留）
2. **智能选题**：OpenAlex 按相关性+引用排序，**同篇多记录去重合并**（预印本/正式版，优选 arXiv 直链），
   再按查询意图**自动决定篇数**（精确标题→少而精，话题→多给候选）
3. **取全文**：有 arXiv 版走 arXiv 直链；OpenAlex 给的出版商链下不动时，**用标题回查 arXiv 兜底**；
   都拿不到则用摘要兜底
4. **解析**：MinerU 把 PDF 解析成结构化 Markdown（多篇走**批量解析**，模型只装载一次）
5. **摘要**：DeepSeek 用 Map-Reduce 生成结构化摘要（问题/方法/结果/贡献）+ 关键词 + 思维导图
6. 在 Streamlit 界面展示，支持单视图（4 个 tab）与 PDF 对照阅读两种模式，并标注**全文来源**（arXiv/出版商/仅摘要）

整条流水线：`search_papers() → parse_pdfs() → summarize_paper() → UI 展示`

> 检索增强（改写 + OpenAlex）由环境变量开关控制，`start.bat` 已默认开启；关掉则回到纯 arXiv 关键词检索。
> 细节见 [IMPROVEMENTS.md](IMPROVEMENTS.md)。

---

## 二、项目结构

```
AI_Paper_Reader/
├── app.py                      # 主入口：状态管理 / Pipeline 编排 / 侧栏 / 路由
├── start.bat                   # 一键启动脚本：注入 conda 环境 PATH + 自检后启动
├── requirements.txt
├── README.md
├── REMOTE_ACCESS.md            # 组员远程访问指南（Tailscale，可直接转发给组员）
├── GITHUB_GUIDE.md             # 组员 git 拉取/更新指南
├── IMPROVEMENTS.md             # 改进备忘录（已实现项 + 后续方向）
├── .gitignore
├── .streamlit/
│   └── config.toml             # 深色主题配置
├── contracts/                  # 接口契约（门面层，含 USE_MOCK 开关）
│   ├── search_contract.py
│   ├── parse_contract.py
│   └── llm_contract.py
├── agents/                     # 各模块真实实现
│   ├── __init__.py             # 空文件，让 agents 成为可导入的包
│   ├── search_agent.py         # 2号位：检索编排 + 下载（OpenAlex/arXiv，含自动篇数/arXiv 兜底）
│   ├── openalex_agent.py       #         OpenAlex 智能选题 + 去重合并（S2 免审批平替）
│   ├── query_rewriter.py       #         自然语言/中文 → 英文检索词（DeepSeek）
│   ├── semantic_agent.py       #         Semantic Scholar 版（可选后备，需 key）
│   ├── pdf_parser.py           # 3号位：MinerU 解析（单篇 parse_pdf + 批量 parse_pdfs）
│   ├── llm_agent.py            # 4号位：DeepSeek 摘要（Map-Reduce，带 system 提示词）
├── tests/
│   └── smoke.py                # 冒烟测试：纯逻辑回归，无需网络/key（python tests/smoke.py）
├── cache/                      # 检索/摘要缓存 + arxiv_title_map.json（git 忽略）
├── components/
│   ├── styles.py               # 全部 CSS（蓝紫红主题，配色令牌化）
│   └── views.py                # 三个 view 渲染函数 + 思维导图/PDF/全文来源辅助
├── presentation/               # 发布会风格展示页（showcase.html，离线）+ 交接文档
└── downloads/                  # 下载的 PDF + MinerU 生成的 md 缓存（git 忽略）
```

### 契约门面层（重要）

`contracts/` 下三个文件是**门面**，顶部各有一个 `USE_MOCK` 开关：

- `USE_MOCK = False` → 引用 `agents/` 下的真实实现
- `USE_MOCK = True`  → 用文件内的 Mock 假数据（离线开发 / demo 兜底 / 联调时隔离故障模块）

`app.py` 只认 `contracts/`，切换实现只改这一个开关，主程序和队友代码都不用动。

---

## 三、环境要求

| 项目 | 要求 / 本机验证值 |
|------|------------------|
| 操作系统 | Windows |
| Python | 建议用 conda 环境（本项目环境名 `mineru_new`） |
| Streamlit | **≥ 1.39**（用到了 `st.segmented_control`） |
| GPU | 本机 RTX 5060（Blackwell, sm_120） |
| CUDA Toolkit | 13.2 |
| PyTorch | 2.11.0+cu130 |
| MinerU | 3.1.0 |
| 网络 | **访问 arXiv 建议全局代理**（国内直连 export.arxiv.org 有时会读超时） |

> ⚠️ MinerU 解析后端固定使用 **pipeline**。不要用默认的 `hybrid-auto-engine` 或
> `vlm-auto-engine`，它们依赖 lmdeploy/turbomind，与本机 CUDA 13 不兼容
> （`ImportError: DLL load failed while importing _turbomind`）。详见踩坑记录。

---

## 四、快速开始

### 1. 安装依赖

```bash
conda activate mineru_new
cd /e/AI_Paper_Reader
pip install -r requirements.txt
```

MinerU 较重，若 `requirements.txt` 中已注释，需单独安装：

```bash
pip install mineru
```

### 2. 设置 DeepSeek API Key（环境变量，切勿写进代码）

在**启动 Streamlit 的同一个终端**里设置（本机默认终端是 PowerShell）：

```powershell
$env:DEEPSEEK_API_KEY="你的key"      # PowerShell
```

```bash
export DEEPSEEK_API_KEY=你的key      # Git Bash / CMD 用 set DEEPSEEK_API_KEY=你的key
```

> Key 必须走环境变量。**任何情况下都不要把 key 写进代码或文档文件并提交到 git。**
> 验证：PowerShell `echo $env:DEEPSEEK_API_KEY`、Git Bash `echo $DEEPSEEK_API_KEY` 能打印出来。

### 3. 确认网络（arXiv 需要代理）

国内直连 `export.arxiv.org` 会 `read timeout`。**请开启全局代理**后再运行。
验证：浏览器能打开
`https://export.arxiv.org/api/query?search_query=all:RAG&max_results=3`
并返回 XML，即说明网络通畅。

### 4. 启动

**推荐用一键脚本**（已帮你把 conda 环境注入 PATH，保证子进程能找到 `mineru`）：

```powershell
.\start.bat
```

> `start.bat` 顶部有一行 `CONDA_ENV_DIR`，换机器/换环境名时只改这一行。
> 它还会在启动前自检 `mineru` 与 `DEEPSEEK_API_KEY`，缺啥会提示。

或手动启动（必须先 `conda activate mineru_new`，否则解析子进程找不到 `mineru`，详见踩坑记录 5）：

```bash
conda activate mineru_new
streamlit run app.py
```

浏览器打开后，在起始页输入关键词或点示例 chip 即可。

> 想让组员远程访问这个 demo（不分城市），见 [REMOTE_ACCESS.md](REMOTE_ACCESS.md)
> ——用 Tailscale，3 步接入，可直接把那份文档转发给组员。

---

## 五、运行时机制（理解这些能少踩坑）

### 三层缓存（核心性能机制）

本项目每一层都做了缓存，**冷启动慢、热启动极快**：

| 层 | 缓存内容 | 缓存位置 | 效果 |
|----|---------|---------|------|
| 检索 | 论文元数据（按 query+max_results+来源） | `cache/search_*.json` / `search_oa_*.json` | 命中后跳过检索请求（OpenAlex/arXiv），秒回且不依赖外网 |
| 解析 | MinerU 生成的 md | 与 PDF 同目录同名 `.md` | 命中后 parse 从 ~130s/篇 → 0.4s |
| 摘要 | DeepSeek 结构化输出 | `cache/*.json`（相对启动目录，须从项目根启动） | 命中后秒回 |

实测：3 篇论文冷跑约 **9 分钟**（parse 占 70%），**热跑 0.4 秒**。
（多篇冷跑因 MinerU 批量解析"模型只装一次"会更快，见下。）

> **Demo 策略**：演示前先用要展示的关键词跑一遍，把三层缓存全部预热好。
> 当天搜同样的词，全程几秒出结果。篇数默认由「自动调整篇数」开关按查询意图决定；
> 想固定篇数可在侧栏「设置」关掉该开关，再用滑块设 1~2 篇。

### MinerU 环境注入

`pdf_parser.py` 通过 subprocess 调用 mineru CLI，会在子进程环境里自动注入：

- 移除无效的 `SSL_CERT_FILE`（见踩坑记录）
- `MINERU_MODEL_SOURCE=modelscope`（国内模型源）
- `MODELSCOPE_CACHE=D:/MinerU_Models`（模型缓存目录，**机器相关，换机器需改**）
- `CUDA_PATH`（仅在外部未设置时补默认值）

这些默认值在 `pdf_parser.py` 顶部常量，也都支持外部环境变量覆盖。

### MinerU 批量解析（多篇时自动启用）

MinerU 最大的开销是**每次启动重新加载模型**。多篇论文时，`parse_pdfs()` 把未命中缓存的
PDF 合并为**一次 `mineru -p <目录>` 调用**（目录模式），模型只装载一次，N 篇显著快于逐篇。
命中 md 缓存的不进批；批量整体失败会**自动回退逐篇**，保证健壮。单篇 `parse_pdf()` 契约不变。

### LLM 摘要 Map 章节级并发

摘要的 Map 阶段（逐章节小结）是 I/O 密集（等 DeepSeek），改为线程池并发，一篇 25~30 节
不再串行干等。结果按章节顺序严格保持。并发数 `MAP_CONCURRENCY`（默认 5，**设 1 = 串行**），
有界以尊重 DeepSeek 限流（429 由已有退避兜底）。实测真实论文约 2.6x。

### 检索增强相关缓存与开关（`start.bat` 已默认开启）

| 环境变量 | 作用 |
|---------|------|
| `USE_QUERY_REWRITE=1` | 开「自然语言/中文 → 英文检索词」改写 |
| `USE_OPENALEX=1` | 用 OpenAlex 智能选题（去重合并 + 引用排序） |
| `OPENALEX_MAILTO=邮箱` | 进 OpenAlex polite pool，限流更宽 |

> OpenAlex 给的出版商链（如 AAAI）下不动时，会用标题回查 arXiv 兜底，结果落盘
> `cache/arxiv_title_map.json`（含负缓存），同一篇不重复打 arXiv。

---

## 六、踩坑记录（重要，遇到报错先查这里）

### 1. `FileNotFoundError: [Errno 2]` 指向 ssl / cacert.pem

**现象**：MinerU 或 DeepSeek 调用启动即崩，traceback 末尾是
`ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])`。

**原因**：conda 激活环境时设了 `SSL_CERT_FILE`，指向
`...mineru_new/ssl/cacert.pem`，但该文件不存在。httpx 建 SSL 时读它就崩。
（注意：它不在系统环境变量里，是 conda 激活时动态注入的，在"设置"里找不到。）

**处理**：代码已做防御——`pdf_parser.py` 在子进程环境里 pop 掉它，
`llm_agent.py` 在创建 client 前检测到无效值就清掉。新机器若仍报此错，
可手动 `unset SSL_CERT_FILE` 验证。

### 2. `ImportError: DLL load failed while importing _turbomind`

**现象**：用 `-b vlm-auto-engine` 或默认 backend 解析时崩。

**原因**：MinerU 3.x 默认 backend 走 lmdeploy/turbomind，其预编译版本与本机
CUDA 13 不兼容。

**处理**：固定用 `-b pipeline`（代码已固定）。pipeline 不依赖 turbomind，
且 torch 是 cu130 时其 OCR 仍走 GPU，是本机唯一稳定可用的后端。

### 3. arXiv 检索 `read timeout`

**现象**：`RuntimeError: arXiv API 请求失败: The read operation timed out`，
或 `HTTP 429`（限流，共享代理出口 IP 上较常见）。

**原因**：国内直连 export.arxiv.org 不稳/不通（超时）；或请求过密 / 共享
出口 IP 被限流（429）。

**处理**：
1. 开全局代理（治超时）。
2. `search_agent.py` v1.1 已内置应对：**超时→快速重试**、**429/5xx→指数退避**、
   全局 **≥3s 限速**（遵守 arXiv 官方频率要求），偶发抖动可自愈。
3. **检索结果已落盘缓存**：搜过的词命中 `cache/search_*.json` / `search_oa_*.json` 直接跳过检索请求，
   演示前预热好，当天外网挂了也能出结果。
4. 可调环境变量：`ARXIV_TIMEOUT`(30) / `ARXIV_MAX_RETRY`(3) / `ARXIV_MIN_INTERVAL`(3) /
   `ARXIV_SEARCH_CACHE`(1) / `ARXIV_SEARCH_CACHE_TTL`(0=永不过期)。
5. **OpenAlex 模式下的 arXiv 兜底也会触发此坑**：选题命中一堆出版商独占论文（如 AAAI）时，
   每篇都回查 arXiv 易招超时/429。已三重缓解——OpenAlex **去重合并优选 arXiv 直链**（从源头少触发）、
   **标题兜底落盘缓存**（`arxiv_title_map.json`，不重复打）、**快速失败**（`ARXIV_FALLBACK_TIMEOUT`(12)/
   `ARXIV_FALLBACK_RETRY`(1)）+ 反爬域名黑名单跳过首次下载。仍卡顿可调小这两个兜底变量。

### 4. MinerU "正在解析"卡很久但 GPU 不动

**原因**：多半是上面第 1 或第 3 个问题导致子进程在等网络/SSL 超时，并非真在解析。

**处理**：先去命令行单独裸跑 mineru 看真实日志（见下方"单独测试"），
不要在 Streamlit 里盲等。

### 5. 解析每篇都"失败"，报"未找到 mineru 命令 / 请确认已安装 MinerU"

**现象**：Streamlit 里解析成功 0/N，每篇标"失败"；或 `python agents/pdf_parser.py`
报 `未找到 mineru 命令`——但 `pip list` 明明装了 MinerU。

**原因**：`pdf_parser.py` 用 subprocess 以**裸命令 `mineru`** 调用，靠 PATH 解析。
只有 **`conda activate mineru_new` 后**（环境的 `Scripts\` 进了 PATH）才找得到
`mineru.exe`。直接用 `python.exe` 跑、或在没激活的终端启动 Streamlit，PATH 里没有
`Scripts\`，子进程就找不到 mineru，于是每篇静默失败。报错文案"请确认已安装"有误导性，
**更常见的真因是环境没激活**。

**处理**：用 `.\start.bat` 启动（已自动注入 PATH 并自检）；或手动启动前务必先
`conda activate mineru_new`。验证：`where mineru` 能打印出
`...\envs\mineru_new\Scripts\mineru.exe`。

---

## 七、分模块单独测试

### 冒烟测试（改完代码先跑这个）

纯逻辑回归，**无需网络 / API key**，一条命令确认核心逻辑没回归：

```bash
python tests/smoke.py        # 退出码 0=全过
```

覆盖：自动篇数意图判定 / OpenAlex 去重合并 / 查询改写回退 / PDF 后处理与批量入口 /
arXiv 标题兜底缓存 / LLM Map 并发顺序。不覆盖真实 MinerU/DeepSeek/联网（那些靠下方分层手测 + 缓存）。

遇到问题时，**逐层隔离**比在 Streamlit 里盲调高效得多。

### 单独测检索

```bash
python -c "
from agents.search_agent import search_papers
r = search_papers('RAG', max_results=3)
print('检索到', len(r), '篇')
for p in r: print(' -', p['title'][:50], '| local:', bool(p['local_path']))
"
```

### 单独测解析（裸跑 mineru，日志最全）

```bash
unset SSL_CERT_FILE
export MINERU_MODEL_SOURCE=modelscope
export MODELSCOPE_CACHE="D:/MinerU_Models"
mineru -p "downloads/某篇.pdf" -o "E:/temp/out" -b pipeline
```

或用项目封装：`python agents/pdf_parser.py "downloads/某篇.pdf"`

### 单独测摘要（用已解析的论文喂给 LLM）

```bash
python -c "
from agents.pdf_parser import parse_pdf
from agents.llm_agent import summarize_paper
d = parse_pdf(r'downloads/某篇.pdf')
r = summarize_paper(d, lang='en')
print('摘要OK:', r['one_sentence'])
"
```

### 解析时盯 GPU

```bash
nvidia-smi -l 1      # 看 GPU-Util 利用率，判断在真解析还是在等待
```

---

## 八、团队协作约定

### 接口契约不可私自修改

`contracts/` 中的**函数名、参数名、返回字段名**已冻结，是各模块协作的边界。
任何字段格式变更（例如曾经 `sections` 从 dict 改为 list[dict]）**必须提前
通知集成方与相关位**，不可默默改动。

### 各位职责

| 位 | 负责人 | 模块 | 契约 |
|----|--------|------|------|
| 1号位 | （集成） | UI / Pipeline 集成 | 消费所有契约 |
| 2号位 | — | 检索 + 下载（OpenAlex/arXiv） | `search_contract.py` |
| 3号位 | — | PDF 解析（MinerU） | `parse_contract.py` |
| 4号位 | — | DeepSeek 摘要 | `llm_contract.py` |
| 5号位 | — | 测试 + 展示页 | — |

### 修改建议用分支

研究高风险改动（如批处理优化）请开新分支，不要直接动主分支：

```bash
git checkout -b feature/batch-parsing
```

主分支始终保留可运行的稳定版作为回退点。

### 提交前检查清单

- [ ] 代码和文档里**没有任何 API Key**（包括 git 历史；不确定就吊销重发）
- [ ] `.gitignore` 已忽略 `downloads/`、`cache/`、`__pycache__/`（注：摘要缓存在项目根 `cache/`，没有 `agents/cache/`）
- [ ] `git status` 确认没有混入 PDF、json 缓存、大文件、key
- [ ] commit message 清晰（尤其是稳定版要标注）

---

## 九、待办 / 未来方向

- [x] 检索结果缓存（按 query 存 json，命中跳过检索请求，降低对代理的依赖）
      —— ✅ 已实现（`search_agent.py`，缓存于 `cache/search_*.json` / `search_oa_*.json`）
- [x] 检索增强：Query Rewriter（自然语言/中文→英文检索词）+ OpenAlex 智能选题
      —— ✅ 已实现（`agents/query_rewriter.py`、`agents/openalex_agent.py`，开关
      `USE_QUERY_REWRITE` / `USE_OPENALEX` / `OPENALEX_MAILTO`，`start.bat` 默认开）。
      含**去重合并**（同篇多记录，优选 arXiv 直链）、**arXiv 标题兜底**、**按意图自动篇数**。
      S2 版 `agents/semantic_agent.py` 保留为可选后备。详见 [IMPROVEMENTS.md](IMPROVEMENTS.md) 第 2 节
- [x] 改写/摘要加 **system 提示词**（`_call_deepseek` 支持 system 角色，指令更稳）；
      界面标注**全文来源**、app 视觉优化（配色令牌化/字号/可访问性）；加**冒烟测试** `tests/smoke.py`
- [x] MinerU 批处理（目录模式，模型只装载一次）—— ✅ 已实现（`parse_pdfs`，批失败自动回退逐篇）
- [x] LLM 摘要 Map 章节级并发（`MAP_CONCURRENCY`，默认 5，设 1=串行）—— ✅ 已实现
      （`llm_agent.py` 线程池，顺序严格保持；实测真实论文约 2.6x）
- [ ] MinerU 进阶：常驻 api 服务 + 多篇并发，喂满闲置 GPU（高风险，建议在分支研究）
- [ ] LLM 论文级并发（多篇同时摘要，需重构 app.py 进度条编排）
- [ ] 可选功能：搜索历史、单篇重试、多模型切换、笔记 tab

> 注：批处理等优化主要改善**冷启动**，而冷启动已被多层缓存摊销（热跑 0.4s）。
> 生产系统会用异步任务队列 + 预计算 + 强算力把重活移出请求路径，本项目在
> 课程范围内用多层缓存实现了同等的"算过不重算"思想。是否进一步优化按需权衡。

---

## 十、常用命令速查

```bash
# 启动（推荐一键脚本，自动注入 PATH + 自检）
#   PowerShell: $env:DEEPSEEK_API_KEY="你的key";  .\start.bat
# 或手动：
conda activate mineru_new
export DEEPSEEK_API_KEY=你的key          # PowerShell: $env:DEEPSEEK_API_KEY="你的key"
streamlit run app.py

# 单测各层
python agents/pdf_parser.py "downloads/xxx.pdf"
python -c "from agents.search_agent import search_papers; print(len(search_papers('RAG',3)))"

# 看 GPU
nvidia-smi -l 1

```