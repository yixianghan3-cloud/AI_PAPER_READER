# 通过 GitHub 获取 / 更新源码

> 适合**想本地自己跑、参与改代码**的同学。
> 只想用 demo 看效果的，走 [REMOTE_ACCESS.md](REMOTE_ACCESS.md) 即可，不必拉代码。

仓库地址：

```
https://github.com/yixianghan3-cloud/AI_PAPER_READER.git
```

---

## 0. 前提

- 本机已安装 **Git**（没装：<https://git-scm.com/downloads>，或 `winget install Git.Git`）。
- 若仓库是 **private**，需要作者在 GitHub 上把你加为 **Collaborator**
  （仓库 → Settings → Collaborators → Add people），否则 clone 会要求授权或失败。
- ⚠️ **以作者已把最新代码 push 到该仓库为前提**，你 pull 到的才是最新版
  （含 `REMOTE_ACCESS.md`、`start.bat`、最新 `README.md` 等）。

---

## 1. 首次获取（clone）

在你想存放项目的目录下执行：

```bash
git clone https://github.com/yixianghan3-cloud/AI_PAPER_READER.git
cd AI_PAPER_READER
```

## 2. 后续更新（pull）

进入项目目录，拉取作者的最新改动：

```bash
git pull
```

---

## 3. 拉下来之后做什么

- **想远程用 demo**：看 [REMOTE_ACCESS.md](REMOTE_ACCESS.md)（装 Tailscale，免搭环境）。
- **想本地自己跑**：看 [README.md](README.md) 的「三、环境要求 / 四、快速开始 / 六、踩坑记录」。
  本地跑需要自建 `mineru_new` conda 环境、装 MinerU + PyTorch、配自己的 `DEEPSEEK_API_KEY`，坑较多，按 README 逐条来。

---

## 常见问题

- **clone 报权限 / 认证失败**：private 仓库需先被加为 Collaborator，并用 GitHub 账号认证
  （浏览器登录、`gh auth login`，或用 Personal Access Token 作为密码）。
- **pull 提示冲突 / 本地有改动**：先 `git stash` 暂存自己的改动再 `git pull`；
  或 `git status` 看清楚再处理。
- **没有 PDF / 缓存很正常**：`downloads/` 和 `cache/` 已被 `.gitignore` 忽略，
  不会同步；首次本地跑是冷启动（MinerU 单篇约 90 秒），属正常现象。
