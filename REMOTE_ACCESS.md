# 远程访问指南(Tailscale)

> 本文档面向**演示主机方(项目作者)**与**组员(访问方)**两类人。
> 校园网(sdu_net)开了客户端隔离,普通局域网互联不通,因此统一用 **Tailscale**
> 这个点对点加密 VPN 来访问,不分城市、无需公网 IP、无需改路由器。

---

## 〇、它是怎么工作的(先理解,少踩坑)

```
        组员的电脑                         演示主机(项目作者这台)
   ┌──────────────────┐   Tailscale 加密隧道   ┌────────────────────────────┐
   │  浏览器           │ ───────────────────▶ │  Streamlit  :8501           │
   │  http://100.100. │                       │  ├─ MinerU 解析(用 GPU)     │
   │   176.28:8501     │ ◀─────────────────── │  └─ DeepSeek 摘要(用 API Key)│
   └──────────────────┘                       └────────────────────────────┘
```

- **真正干活的是主机这台**:检索 / MinerU 解析(吃 GPU)/ DeepSeek 摘要(用主机上的 API Key)全在主机跑。
- **组员只是开一个网页**,所以组员本地**不需要**装 Python / MinerU / 配 Key,什么都不用装(除了 Tailscale)。
- 主机这台必须**全程开机、服务在跑、不休眠**,组员才连得上。

> 关键地址(本机固定值,记住即可):
> - Tailscale IP:`100.100.176.28`
> - MagicDNS 名:`laptop-ivu92ivk.tail909a69.ts.net`
> - 端口:`8501`

---

## 一、主机方(项目作者)操作

### 1. 邀请组员加入你的 tailnet

本项目已为 2 / 3 / 5 号位生成好邀请链接（4 号位已加入），见下方「二、组员方 → 0. 认领你的专属邀请链接」对照表，直接发给对应组员即可。

如需给新成员**再生成**链接：

1. 浏览器打开 Tailscale 管理后台:<https://login.tailscale.com/admin/users>
2. 点 **Invite users(邀请用户)**,生成邀请链接。
3. 把链接发给对应组员。他们点链接注册/登录后,就和你在**同一个 tailnet**,才能看到并访问你这台机器。

> 只有同一个 tailnet 内的设备能互相访问。没收到邀请、或登的是别的账号,都会连不上。

### 2. 防止电脑休眠(很重要)

演示期间电脑一睡,组员立刻断连。
`设置 → 系统 → 电源` →「接通电源时,使设备进入睡眠状态」改为「**从不**」;
笔记本记得**插上电源**。

### 3. 设置 API Key 并启动服务

在 PowerShell 里(在项目根目录 `E:\AI_Paper_Reader`):

```powershell
$env:DEEPSEEK_API_KEY="你的key"
.\start.bat
```

看到下面这几行就说明起来了(别关这个窗口):

```
You can now view your Streamlit app in your browser.
  Local URL:   http://localhost:8501
  Network URL: http://172.25.235.185:8501
```

> `start.bat` 会自动注入 conda 环境、自检 `mineru` 和 `DEEPSEEK_API_KEY`;
> 缺啥会打印 `[WARN]` 提示。Ctrl+C 可停止。

### 4. 演示前预热缓存(强烈建议)

把你**打算让组员搜的关键词**,自己先在网页里跑一遍(搜一次即可),
让"检索→解析→摘要"三层缓存全部命中。这样组员当天搜同样的词,**1 秒出结果**。

- 已经预热过的词:`RAG`、`transformer`(downloads/ 里已有这些论文的缓存)。
- 直接告诉组员"搜 RAG / transformer",体验最顺。
- 不要让多人**同时**去搜没缓存过的新词:MinerU 冷解析单篇约 90 秒,还会互相排队。

### 5. 确认自己的 Tailscale 在线(可选自检)

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" status
& "C:\Program Files\Tailscale\tailscale.exe" ip -4   # 应输出 100.100.176.28
```

---

## 二、组员方(访问者)操作

### 0. 认领你的专属邀请链接（先做这步）

点开**属于你那一行**的链接，注册 / 登录 Tailscale，即可加入同一个 tailnet。
链接是一次性的、按位号分配，**请认领自己的，不要点别人的**：

| 位号 | 邀请链接 |
|------|----------|
| 2 号位 | <https://login.tailscale.com/uinv/iGxe8kXxtT11cfTjKK3ZA11> |
| 3 号位 | <https://login.tailscale.com/uinv/iK6L4z48mB11cfTjKK3ZA11> |
| 5 号位 | <https://login.tailscale.com/uinv/iGbqmM4AbL11cfTjKK3ZA11> |
| 4 号位 | ✅ 已加入，无需再点 |

> 链接失效或点错了，找主机方（项目作者）在 [admin 后台](https://login.tailscale.com/admin/users) 重新生成一个。

### 1. 安装 Tailscale

- Windows / macOS:<https://tailscale.com/download>
- 手机(iOS/Android):应用商店搜 **Tailscale**
- 安装后**用主机方邀请你的那个邀请链接登录**(或登录后接受邀请),确保和主机在同一 tailnet。

### 2. 打开网页

浏览器访问(推荐用 IP,最稳):

```
http://100.100.176.28:8501
```

或用域名(需你本地开启 MagicDNS,Tailscale 默认开):

```
http://laptop-ivu92ivk.tail909a69.ts.net:8501
```

> ⚠️ 注意是 **http**(不是 https)、**别漏端口 :8501**。

### 3. 使用

- 在起始页输入关键词(建议先搜主机方让你搜的、已缓存的词,如 `RAG`),点「开始」。
- 几秒内出结果:左侧论文列表,右侧 5 个标签页(摘要 / 思维导图 / 关键词 / 解析后文本 / 原始 PDF)。
- 多人各自打开互不影响(每人独立会话)。

### 4. 连不上时先自测(可选)

```
tailscale ping 100.100.176.28
```

通了说明 Tailscale 链路 OK,问题在网页/服务;不通就是 Tailscale 没连好(见排查)。

---

## 三、常见问题排查

| 现象 | 可能原因 / 处理 |
|------|----------------|
| 网页完全打不开、转圈到超时 | ① 主机的 `start.bat` 窗口是否还开着、服务在跑?② 双方 Tailscale 都登录、且在**同一 tailnet**?③ 主机是否休眠/关机/断网?④ 先用 IP `100.100.176.28:8501`,别用域名。 |
| `tailscale ping` 不通 | 组员没真正加入 tailnet,或登错账号。重新点邀请链接、确认 `tailscale status` 里能看到主机 `laptop-ivu92ivk`。 |
| 域名打不开但 IP 能开 | 组员没开 MagicDNS。直接用 IP `100.100.176.28:8501` 即可。 |
| 搜索后"解析中"很久 | 搜了**没缓存**的新词,MinerU 在冷解析(单篇约 90s),多人同时更慢。改搜已预热的词(RAG/transformer),或耐心等。 |
| 每篇"解析失败 0/N" | 主机端环境没激活(mineru 没进 PATH)。主机请用 `.\start.bat` 启动,而不是手动 `streamlit run`。 |
| 摘要标"失败" | 主机端 `DEEPSEEK_API_KEY` 没设或失效;或代理没开导致请求失败。 |
| 能开网页但搜新词报检索超时 | 主机端访问 arXiv 需要**全局代理**在线;只演示已缓存的词则不依赖代理。 |

---

## 四、安全注意

- **只在 tailnet 内开放**:当前设置下服务只对你邀请进 tailnet 的人可见,校园网/公网的人访问不到(防火墙 `Tailscale-In` 仅放行 Private 接口,校园网是 Public)。
- **不要开 Tailscale Funnel**:`tailscale funnel` 会把服务暴露到**整个公网**,会被陌生人访问、消耗你的 DeepSeek token,demo 一律不用。
- **演示结束后收尾**:
  - 主机端 `Ctrl+C` 停掉 Streamlit。
  - 不再需要时,可在 [admin 后台](https://login.tailscale.com/admin/users)把临时组员从 tailnet 移除。

---

## 五、快速核对清单

**主机方(你)**
- [ ] 组员已被邀请进 tailnet(`tailscale status` 能看到他们)
- [ ] 电源已设为不休眠 / 已插电
- [ ] `DEEPSEEK_API_KEY` 已设,`.\start.bat` 已启动且无 `[WARN]`
- [ ] 要演示的关键词已预热缓存
- [ ] (搜新词时)全局代理已开

**组员方**
- [ ] 已装 Tailscale 并用邀请账号登录
- [ ] `tailscale ping 100.100.176.28` 通
- [ ] 浏览器打开 `http://100.100.176.28:8501`(http、带 :8501)
