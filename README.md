<div align="center">

# 📖 AI Paper Reader · 学术论文智能摘要系统

**输入一句话，秒出结构化摘要与思维导图** —— 中文/自然语言/论文标题皆可，自动完成检索、解析、摘要、可视化。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![MinerU](https://img.shields.io/badge/Parse-MinerU%203.1-5DCAA5)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-7F77DD)
![OpenAlex](https://img.shields.io/badge/Search-OpenAlex%20%2F%20arXiv-b06ab3)

</div>

---

## 简介

把"读一篇论文从一下午到一分钟"。给定关键词、中文研究方向或论文标题，系统自动从 OpenAlex / arXiv
检索相关论文、用 MinerU 解析全文、再由 DeepSeek 生成**结构化摘要 + 思维导图**，并在 Streamlit
界面中以多视图呈现。

```
输入：关键词 / 中文研究方向 / 论文标题   （如「我想了解大模型如何减少幻觉」）
  ↓
🔎 智能检索   ·  OpenAlex + arXiv（去重合并、按意图自动定篇数）
  ↓
📄 PDF 解析   ·  MinerU 批量解析（多篇模型只装载一次）
  ↓
🧠 AI 摘要    ·  DeepSeek Map-Reduce + 章节级并发
  ↓
🖼️ 多视图展示 ·  Streamlit：摘要 / 思维导图 / 关键词 / PDF 对照
```

> 流水线：`search_papers() → parse_pdfs() → summarize_paper() → UI 展示`

---

## ✨ 功能特性

- 🔎 **中文 / 自然语言 / 标题检索** —— LLM 把中文一句话改写成英文检索式；已是干净英文或精确标题则原样保留，避免被改散。
- 🧭 **OpenAlex 智能选题 + 去重合并** —— 按相关性 + 引用排序选题；同一篇论文的预印本/正式版自动合并，优选 arXiv 直链。
- 🪂 **arXiv 标题兜底** —— OpenAlex 给的出版商链下载不动时，用标题回查 arXiv 取全文；结果落盘缓存、快速失败、反爬域名跳过。
- 🎯 **按意图自动定篇数** —— 精确论文标题→少而精，宽泛话题→多给候选，无需手动调参。
- ⚡ **MinerU 批量解析** —— 多篇合并为一次目录模式调用，模型只装载一次；批量失败自动回退逐篇，稳健。
- 🧵 **LLM 摘要 Map 章节级并发** —— 逐章节摘要走线程池，顺序严格保持，实测约 **2.6×** 提速。
- 🗄️ **三层落盘缓存** —— 检索 / 解析 / 摘要各自缓存，冷启动慢、热启动 **~0.4 秒**；解析缓存按标题归一，同篇不同命名也复用。
- 🖼️ **多视图阅读** —— 结构化摘要（问题/方法/结果/贡献）、可交互思维导图、关键词、PDF 原文对照；并标注**全文来源**（arXiv / 出版商 / 仅摘要）。
- 🧱 **契约门面层解耦** —— 三个契约文件各带 `USE_MOCK` 开关，可单独 mock 任一模块，团队并行开发互不阻塞。

---

## 🔄 工作原理

| 步骤 | 做什么 | 模块 |
|------|--------|------|
| 1. 查询改写 | 自然语言/中文 → 英文检索词（可选） | `agents/query_rewriter.py` |
| 2. 智能选题 | OpenAlex 相关性+引用排序，去重合并，自动定篇数 | `agents/openalex_agent.py` |
| 3. 取全文 | arXiv 直链下载；下不动则标题回查 arXiv 兜底；再不行用摘要兜底 | `agents/search_agent.py` |
| 4. 解析 | MinerU 把 PDF 转结构化 Markdown（多篇批量，模型只装一次） | `agents/pdf_parser.py` |
| 5. 摘要 | DeepSeek + Map-Reduce，结构化摘要 + 关键词 + 思维导图 | `agents/llm_agent.py` |
| 6. 展示 | Streamlit 多视图，单视图 / PDF 对照两种模式 | `app.py` / `components/` |

---

## 🚀 快速开始

### 环境要求

| 项目 | 验证环境 |
|------|---------|
| 操作系统 | Windows（conda 环境，本项目名 `mineru_new`） |
| Python | 3.10+ |
| GPU / CUDA | MinerU 解析需要 NVIDIA GPU；本机 RTX 5060 + CUDA 13.2 |
| 关键依赖 | Streamlit ≥ 1.39 · MinerU 3.1 · openai SDK（连 DeepSeek） |
| 网络 | 访问 arXiv 建议全局代理（国内直连 `export.arxiv.org` 偶发读超时） |

> ⚠️ MinerU 后端固定用 **pipeline**（代码已固定）。默认的 `hybrid/vlm-auto-engine` 依赖
> lmdeploy/turbomind，与较新 CUDA 不兼容会报 `DLL load failed while importing _turbomind`。

### 安装

```bash
conda activate mineru_new
pip install -r requirements.txt
pip install mineru          # MinerU 较重，若 requirements 已注释则单独装
```

### 配置 DeepSeek API Key（走环境变量，切勿写进代码）

```powershell
$env:DEEPSEEK_API_KEY="你的key"     # PowerShell
```
```bash
export DEEPSEEK_API_KEY=你的key     # Git Bash（CMD: set DEEPSEEK_API_KEY=你的key）
```

> 🔑 Key 只走环境变量，**任何情况下都不要写进代码/文档并提交到 git**。

### 运行

```powershell
.\start.bat                        # 推荐：自动注入 conda PATH + 自检 + 默认开启检索增强
```
或手动（**必须先 `conda activate mineru_new`**，否则解析子进程找不到 `mineru`）：
```bash
conda activate mineru_new
streamlit run app.py
```

浏览器打开后，在起始页输入关键词 / 中文研究方向 / 论文标题，或点示例 chip 即可。

> `start.bat` 顶部的 `CONDA_ENV_DIR`、`pdf_parser.py` 顶部的 `MODELSCOPE_CACHE` / `CUDA_PATH`
> 等是**机器相关常量**，换机器只改这几处；也都支持外部环境变量覆盖。

---

## ⚙️ 配置（环境变量）

| 变量 | 默认 | 作用 |
|------|------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek 密钥（摘要 + 查询改写必需） |
| `USE_OPENALEX` | `start.bat` 开 | 用 OpenAlex 智能选题（去重 + 引用排序）；关掉回退纯 arXiv |
| `USE_QUERY_REWRITE` | `start.bat` 开 | 中文/自然语言 → 英文检索词改写 |
| `OPENALEX_MAILTO` | — | 填邮箱进 OpenAlex polite pool，限流更宽 |
| `MAP_CONCURRENCY` | `5` | 摘要 Map 章节并发数；设 `1` = 串行 |
| `ARXIV_TITLE_FALLBACK` | `1` | 出版商链下不动时用标题回查 arXiv |
| `ARXIV_FALLBACK_TIMEOUT` / `_RETRY` | `12` / `1` | 兜底查询的超时/重试（快速失败） |
| `MINERU_TIMEOUT` | `300` | 单篇解析超时（秒） |
| `MINERU_CACHE` / `ARXIV_SEARCH_CACHE` | `1` | 解析 / 检索缓存开关 |

---

## 📁 项目结构

```
AI_Paper_Reader/
├── app.py                      # 主入口：状态管理 / Pipeline 编排 / 侧栏 / 路由
├── start.bat                   # 一键启动：注入 conda PATH + 自检后启动
├── contracts/                  # 接口契约（门面层，含 USE_MOCK 开关）
│   ├── search_contract.py · parse_contract.py · llm_contract.py
├── agents/                     # 各模块真实实现
│   ├── search_agent.py         # 检索编排 + 下载（自动篇数 / arXiv 兜底）
│   ├── openalex_agent.py       # OpenAlex 智能选题 + 去重合并
│   ├── query_rewriter.py       # 自然语言/中文 → 英文检索词
│   ├── semantic_agent.py       # Semantic Scholar 版（可选后备，需 key）
│   ├── pdf_parser.py           # MinerU 解析（单篇 parse_pdf + 批量 parse_pdfs）
│   └── llm_agent.py            # DeepSeek 摘要（Map-Reduce + 并发 + system 提示词）
├── components/
│   ├── styles.py               # 全部 CSS（蓝紫红主题，配色令牌化）
│   └── views.py                # 视图渲染 + 思维导图 / PDF / 全文来源辅助
├── tests/smoke.py              # 冒烟测试：纯逻辑回归，无需网络/key
├── presentation/               # 发布会风格展示页（showcase.html，离线）
├── cache/  · downloads/        # 缓存 / 下载的 PDF + md（均 git 忽略）
└── IMPROVEMENTS.md · REMOTE_ACCESS.md · GITHUB_GUIDE.md
```

**契约门面层**：`app.py` 只认 `contracts/`，每个契约顶部一个 `USE_MOCK` 开关——
`False` 用 `agents/` 真实现，`True` 用文件内 Mock 假数据（离线开发 / demo 兜底 / 隔离故障模块）。

---

## 🧪 测试

```bash
python tests/smoke.py        # 冒烟测试：纯逻辑回归，无需网络/key，退出码 0=全过
```
覆盖：自动篇数判定 / OpenAlex 去重合并 / 查询改写回退 / PDF 后处理与批量入口 / arXiv 兜底缓存 /
解析缓存键归一 / LLM Map 并发顺序。真实 MinerU / DeepSeek / 联网靠下方分层手测：

```bash
# 检索
python -c "from agents.search_agent import search_papers; print(len(search_papers('RAG',3)))"
# 解析（裸跑 mineru，日志最全）
python agents/pdf_parser.py "downloads/某篇.pdf"
# 摘要
python -c "from agents.pdf_parser import parse_pdf; from agents.llm_agent import summarize_paper; print(summarize_paper(parse_pdf('downloads/某篇.pdf'))['one_sentence'])"
```

---

## ⚡ 性能

| 指标 | 数值 | 说明 |
|------|------|------|
| 解析加速比 | **90s → 0.4s** | 冷解析 ~90–100s/篇；命中缓存 ~0.4s |
| 摘要并发提速 | **~2.6×** | Map 章节级线程池并发实测 |
| 缓存层数 | **3 层** | 检索 / 解析 / 摘要各自落盘 |

> **Demo 建议**：演示前先用要展示的词跑一遍预热三层缓存，当天搜同词几秒出结果。
> 多篇冷跑因 MinerU 批量解析"模型只装一次"会更快。

---

## 🗺️ 路线图

**已实现**
- [x] 检索增强：查询改写 + OpenAlex 智能选题 + 去重合并 + arXiv 标题兜底 + 按意图自动篇数
- [x] MinerU 批量解析（目录模式，模型只装一次，失败回退逐篇）
- [x] LLM 摘要 Map 章节级并发（`MAP_CONCURRENCY`）
- [x] 三层缓存 + 解析缓存键归一（同篇不同命名复用）
- [x] 改写/摘要 system 提示词、全文来源标注、冒烟测试

**计划中**
- [ ] MinerU 常驻 api 服务 + 多篇并发，喂满闲置 GPU（高风险，建议在分支研究）
- [ ] LLM 论文级并发（多篇同时摘要）
- [ ] 搜索历史 / 单篇重试 / 多模型切换 / 笔记 tab

> 细节与设计权衡见 [IMPROVEMENTS.md](IMPROVEMENTS.md)。

---

## 🔧 故障排查

<details>
<summary><b>解析/摘要启动即崩，traceback 指向 ssl / cacert.pem</b></summary>

conda 激活时注入了 `SSL_CERT_FILE` 指向不存在的 `cacert.pem`，httpx 建 SSL 时读它就崩。
代码已防御（`pdf_parser.py` 子进程 pop、`llm_agent.py` 创建 client 前清除无效值）；
新机器若仍报错可手动 `unset SSL_CERT_FILE` 验证。
</details>

<details>
<summary><b><code>ImportError: DLL load failed while importing _turbomind</code></b></summary>

MinerU 默认 backend 走 lmdeploy/turbomind，预编译版本与较新 CUDA 不兼容。代码已固定
`-b pipeline`（不依赖 turbomind，OCR 仍走 GPU），是兼容性最强的后端。
</details>

<details>
<summary><b>arXiv <code>read timeout</code> 或 <code>HTTP 429</code></b></summary>

国内直连 export.arxiv.org 不稳，或共享出口 IP 被限流。处理：① 开全局代理；
② 代码内置超时快速重试 / 429 指数退避 / ≥3s 限速；③ 检索结果落盘缓存，预热后断网也能出；
④ OpenAlex 兜底招限流时，已用「去重优选 arXiv 直链 + 兜底缓存 + 快速失败 + 反爬黑名单」四重缓解。
</details>

<details>
<summary><b>每篇解析都"失败"，报"未找到 mineru 命令"（但已 pip 安装）</b></summary>

`pdf_parser.py` 用裸命令 `mineru` 调用，靠 PATH 解析。只有 **`conda activate mineru_new` 后**
（环境 `Scripts\` 进 PATH）才找得到 `mineru.exe`。用 `.\start.bat` 启动（自动注入 PATH），
或手动启动前先激活环境。验证：`where mineru` 能打印出 `...\envs\mineru_new\Scripts\mineru.exe`。
</details>

<details>
<summary><b>MinerU "正在解析"卡很久但 GPU 不动</b></summary>

多半是上面的 SSL / 网络问题导致子进程在等超时，并非真在解析。先去命令行裸跑 mineru 看真实日志，
配合 `nvidia-smi -l 1` 看 GPU 利用率判断。
</details>

---

## 👥 团队与协作

接口契约（`contracts/` 的函数名 / 参数名 / 返回字段名）已冻结，是模块协作的边界，**改动须提前通知集成方**。

| 位 | 模块 | 契约 |
|----|------|------|
| 1 号位 | UI / Pipeline 集成 | 消费所有契约 |
| 2 号位 | 检索 + 下载（OpenAlex/arXiv） | `search_contract.py` |
| 3 号位 | PDF 解析（MinerU） | `parse_contract.py` |
| 4 号位 | DeepSeek 摘要 | `llm_contract.py` |
| 5 号位 | 测试 + 展示页 | — |

- 团队远程访问跑在主机上的 demo（免装环境）：见 [REMOTE_ACCESS.md](REMOTE_ACCESS.md)（Tailscale）。
- 拉取 / 更新代码：见 [GITHUB_GUIDE.md](GITHUB_GUIDE.md)。
- 高风险改动请开分支，主分支始终保留可运行稳定版。

---

<div align="center">
<sub>课程项目 · 学术论文智能摘要系统 · Streamlit + OpenAlex/arXiv + MinerU + DeepSeek</sub>
</div>
