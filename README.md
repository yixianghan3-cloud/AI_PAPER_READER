# AI Paper Reader · 学术论文智能摘要系统

> 关键词检索 → PDF 解析 → LLM 摘要 → 思维导图，一站式论文速读工具。
> 技术栈：Streamlit + arXiv API + MinerU + DeepSeek。

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

输入一个研究方向关键词（如 `transformer`、`RAG`），系统自动：

1. 调 arXiv 检索相关论文并下载 PDF
2. 用 MinerU 把 PDF 解析成结构化 Markdown
3. 调 DeepSeek 用 Map-Reduce 生成结构化摘要（问题/方法/结果/贡献）+ 关键词 + 思维导图
4. 在 Streamlit 界面展示，支持单视图（5 个 tab）与 PDF 对照阅读两种模式

整条流水线：`search_papers() → parse_pdf() → summarize_paper() → UI 展示`

---

## 二、项目结构

```
AI_Paper_Reader/
├── app.py                      # 主入口：状态管理 / Pipeline 编排 / 侧栏 / 路由
├── start.bat                   # 一键启动脚本：注入 conda 环境 PATH + 自检后启动
├── requirements.txt
├── README.md
├── REMOTE_ACCESS.md            # 组员远程访问指南（Tailscale，可直接转发给组员）
├── .gitignore
├── .streamlit/
│   └── config.toml             # 深色主题配置
├── contracts/                  # 接口契约（门面层，含 USE_MOCK 开关）
│   ├── search_contract.py
│   ├── parse_contract.py
│   └── llm_contract.py
├── agents/                     # 各模块真实实现
│   ├── __init__.py             # 空文件，让 agents 成为可导入的包
│   ├── search_agent.py         # 2号位：arXiv 检索 + 下载
│   ├── pdf_parser.py           # 3号位：MinerU 解析
│   ├── llm_agent.py            # 4号位：DeepSeek 摘要
├── cache/                      # LLM 摘要缓存（json，git 忽略）
├── components/
│   ├── styles.py               # 全部 CSS
│   └── views.py                # 三个 view 渲染函数 + 思维导图/PDF 辅助
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
| 检索 | （当前未缓存搜索结果，可后续加） | — | — |
| 解析 | MinerU 生成的 md | 与 PDF 同目录同名 `.md` | 命中后 parse 从 ~130s/篇 → 0.4s |
| 摘要 | DeepSeek 结构化输出 | `cache/*.json`（相对启动目录，须从项目根启动） | 命中后秒回 |

实测：3 篇论文冷跑约 **9 分钟**（parse 占 70%），**热跑 0.4 秒**。

> **Demo 策略**：演示前先用要展示的关键词跑一遍，把三层缓存全部预热好。
> 当天搜同样的词，全程几秒出结果。`max_results` 设 1~2 篇即可。

### MinerU 环境注入

`pdf_parser.py` 通过 subprocess 调用 mineru CLI，会在子进程环境里自动注入：

- 移除无效的 `SSL_CERT_FILE`（见踩坑记录）
- `MINERU_MODEL_SOURCE=modelscope`（国内模型源）
- `MODELSCOPE_CACHE=D:/MinerU_Models`（模型缓存目录，**机器相关，换机器需改**）
- `CUDA_PATH`（仅在外部未设置时补默认值）

这些默认值在 `pdf_parser.py` 顶部常量，也都支持外部环境变量覆盖。

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

**现象**：`RuntimeError: arXiv API 请求失败: The read operation timed out`。

**原因**：国内网络直连 export.arxiv.org 不稳/不通。**不是限流**（限流是
HTTP 429）。

**处理**：开全局代理。代理通了就正常。

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
| 2号位 | 张凯诚 | arXiv 检索 + 下载 | `search_contract.py` |
| 3号位 | 郭瑞超 | PDF 解析（MinerU） | `parse_contract.py` |
| 4号位 | — | DeepSeek 摘要 | `llm_contract.py` |
| 5号位 | — | 测试 + 学术海报 | — |

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

- [ ] 检索结果缓存（按 query 存 json，命中跳过 arXiv 请求，降低对代理的依赖）
- [ ] 批处理优化：MinerU 改常驻 api 服务 + 多篇并发，喂满闲置 GPU 算力
      （单篇仅占 ~1G 显存，算力有大量富余；属高风险改动，建议在分支研究）
- [ ] LLM 多篇/多章节并发，压缩摘要阶段耗时
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