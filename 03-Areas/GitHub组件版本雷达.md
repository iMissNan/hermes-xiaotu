---
created: 2026-09-12
updated: 2026-09-16
tags: [区域, 运维, 版本管理]
type: area
status: evergreen
---

# GitHub 组件版本雷达

> 管辖域：本机所有外部血统组件的版本保鲜（GitHub 7 项 + npm/git 镜像运行时 3 项，共 10 项，0912 扩编）。目标：**上游大版本迭代了，我们不能还踩着有 bug 的旧版本**。
> 分工：本卡 = 台账 + 更新 SOP；智能巡检 = Hermes cron「组件版本雷达巡检」（每日 03:30，脚本报告 + agent 分析）；升级动作 = metacubexd 可自主（失败自回滚），其余经权限所有者点头后 agent 执行。

## 巡检与更新纪律（拍板于 2026-09-12，同日升级：周检→每日凌晨+agent 思考）

- **每日 03:30 智能巡检**（cron `b8b613f4ece2`，agent 模式）：脚本 `~/.hermes/scripts/version-radar.py` 先出客观日检报告（只呈现差距不动手），注入值守 agent → **agent 分析决策**：查上游 release notes 判断值不值（安全/bug 修复 vs 纯功能），评估「升级后会不会没法用」（补丁兼容性/数据备份/网络命脉断连），全齐平时只回一行不刷屏。
- **唯一可自主升级项**：metacubexd（无卷无配置纯静态面板）——pull→recreate→验证 9097，失败即用旧镜像 ID 自动回滚。
- **其余全部只给建议**：agent 报「建议升/暂缓/不推荐」+理由+回滚路径，**权限所有者点头才动手**；建议升的判定尤其看补丁锚点是否对新版本仍适用（10Router CN 补丁）、sqlite 是否已备份（Homarr）。
- 每次升级后回填本卡「版本快照」表 + 记一行变更日志（改文件即可，git 提交仍须权限所有者点头）。

## 版本快照（巡检回填，最近核对：2026-09-17）

| 组件 | 血统形态 | 本地 | 上游 | 差距 | 档位 | 详情/升级方法 |
|---|---|---|---|---|---|---|
| Tailscale | Releases 二进制 | **1.102.4** ✅0912升 | v1.102.4 | ✅ 齐平 | 手动 | [[#tailscale 升级 SOP]]（回滚锚点 `tailscaled.bak-1.80.3`） |
| Homarr | ghcr 镜像 | 镜像@2026-09-12 ✅0912升 | v1.77.1 (09-11) | ✅ 已追平 | 手动（有 sqlite+卷） | [[#ghcr 容器升级 SOP]]（db 备份 `~/homarr-appdata-backup-0912`） |
| metacubexd | ghcr 镜像 | 镜像@2026-09-12 | v1.273.1+ (09-10后) | ✅ 已自动更新 | **自动** | [[#metacubexd 自动更新]] |
| ai-token-dashboard | git clone（ghfast 加速） | 17bd359（含本地定制2笔入库）✅0916升 | HEAD e5dbaf6 (09-15) | ✅ 已追平 | 手动 | [[#clone 组件升级 SOP]]（锚点 `.bak-0916`+`.patch`；回滚 reset 3ef3122~1） |
| 10Router | ghcr 镜像 | 1.1.1 (镜像ID 1070a8836c3e) ✅0916升 | v1.1.1 (09-13发) | ✅ 齐平 | 手动（带补丁+db） | [[#ghcr 容器升级 SOP]]（strict-proxy 须 docker cp 重放；备份 `~/10router-backup-0916`；回滚 `:1.1.0` 标签仍在） |
| sing-box | Releases 二进制 | 1.14.0 | v1.14.1 (09-15) | 🔴 落后（值守判暂缓：纯 fix 无安全通告，网络命脉不值凌晨断流） | 手动（网络命脉） | [[#sing-box 升级 SOP]]（.bak-1.14.0 锚点已约定） |
| simplehub | ghcr 镜像 | 容器已停用 | v1.0.2 | ⚪ 被裸机 TokenHub 替代 | 不跟 | 留档 |
| AO编排器 | npm 全局 | 0.19.2 | npm 0.19.2 | ✅ 齐平 | 手动（executor 补丁） | [[#运行时三件套升级 SOP]] |
| hermes-web-ui | npm 全局 | **0.7.21** ✅0916升 | npm 0.7.21 | ✅ 齐平 | 手动（:8648 面板） | [[#运行时三件套升级 SOP]]（回滚 npm install -g hermes-web-ui@0.7.19） |
| hermes-agent本体 | cnb 镜像 git 仓 | **f7cd8bf0 / v0.21.2** ✅0912升 | origin a89c1e11 (09-14) | 🟡 落后846提交(仍是0.21.2滚动) | 手动（官方 `hermes update` 一条龙） | [[#运行时三件套升级 SOP]] |

### 运行时三件套升级 SOP（0912 扩编新增）

- **AO编排器**（`agency-orchestrator`，npm）：本机 `dist/core/executor.js` 打有交接/状态透传补丁，`npm update -g` 整包覆盖=补丁必丢。流程：备份补丁件 → `npm install -g agency-orchestrator@<新>` → 重打补丁（参照 replication 资产 ao-handover 与 `ao-run-safe` 约定）→ 回归 `ao compose`→`ao run` 全链路。回滚=装回旧版本号。
- **hermes-web-ui**（npm）：影响 :8648 网页版（0912 实测：0.7.17→0.7.19 一次过）。流程：`export https_proxy=http://127.0.0.1:7894` → `npm install -g hermes-web-ui@<新> --prefix ~/.npm-global` → `sudo systemctl restart hermes-webui` → curl :8648 出 200 + 日志见 `startup complete` 与会话 stats 读写（=数据无恙）。回滚=装回旧版本号。升级会掉当前网页会话，须挑没人用的时段。npm 二进制在 `~/.local/opt/node23/bin/npm`（`.npm-global/bin` 下没有 npm，别想当然）。
- **hermes-agent 本体**（`~/.hermes/hermes-agent`，git 仓，**官方渠道 `hermes update`**）：0912 实测 v0.21.1→v0.21.2 一条龙成功——自动做 pre-update 状态快照（`~/.hermes/state-snapshots/<ts>-pre-update`）、autostash、git pull、uv 重装依赖、config 格式迁移、并自动重启用户级 hermes-gateway。**毒句与 lark 官方件无需重打**（已进上游/镜像历史）；**但 fry-cards 流式卡片是外挂注入，每次 hermes update 必被冲掉，必须 verify+install 重打**（0913 实锤：v0.21.2 把 gateway/run.py 重构成 run_turn.py 等新文件，且一行锚点拆三行导致 verify 直接报不兼容，需先适配 patcher 再 install）。升级后抽查：prompt_builder 归属句计数=0、Lark 日志 `connected to wss://msg-frontier.feishu.cn`。哨兵会自动体检+飞书告警（见下）。坑：① cnb 镜像会重写上游 commit SHA（同一改动两历史，`merge-base --is-ancestor` 判包含关系而非 SHA 比对）；② 升级后 journal 里 "previous update did not restart gateways" 警告是自检提示**历史**遗留，本次已当场自愈；③ update 会顺手改 config（通知档/delegation 上限），升级后须核对关键设置。回滚=reset 旧 commit + 还原 state-snapshot。`hermes update --check` 可作零风险体检前置。

> 上游数据来自 GitHub API `releases/latest`；ghcr 镜像无版本标签时以镜像构建日期（`docker inspect .Created`）为锚；npm 系走 registry dist-tags；本体仓以 cnb 镜像 origin/main 为锚（fetch 刷新后再比，防假齐平）。

## 升级 SOP（取证自本机实况，2026-09-12）

### ghcr 容器升级 SOP（Homarr / 10Router 通用骨架）

```bash
# 1. 记下当前镜像 ID 作回滚锚点
OLD=$(docker inspect <容器名> --format '{{.Image}}' | cut -c8-19); echo "回滚锚点: $OLD"
# 2. 拉新镜像（ghcr 直连失败时走加速：sed 换前缀，见 DEPLOYMENT 阅读约定）
docker pull <镜像地址>:latest
# 3. 停旧起新 —— 必须用原参数重建（先 docker inspect 导出 Env/Binds/PortBindings 照抄，禁凭记忆）
docker stop <容器名> && docker rm <容器名>
docker run -d --name <容器名> --restart unless-stopped <原端口/卷/env 参数> <镜像地址>:latest
# 4. 验证：端口可达 + 功能抽查；重大版本先 docker logs 看启动报错
# 5. 回滚（若 4 失败）：用 $OLD 镜像 ID 重新 run 一遍原参数
```

- **Homarr 实况参数**：`7575:7575`，卷 `~/.local/opt/homarr/{configs,icons}`，env `DB_URL=/appdata/db/db.sqlite`（sqlite 在容器层内——**升级前必须 `docker cp homarr:/appdata/db ./backup` 备份**，这是它归手动档的原因）。
- **10Router 实况参数**：`20128:20128`，卷 `~/.10router:/app/data` + tailscale bind×2，env 含 `NODE_OPTIONS=--require /app/data/patches/google-oauth-proxy.cjs`（CN 补丁在数据卷里，升级镜像不动补丁，但**大版本后要抽查 Google OAuth 刷新是否仍走代理**）。⚠️ **strictProxy 补丁打在容器层（非卷），任何 `docker stop && rm && run` 重建都会把它冲掉**——包括升级会话收尾的最终重建（0917 实锤：0916 升级白天重放 3 处 PATCHED，当晚 20:29 收尾重建又冲掉，次日哨兵才抓到）。铁律：**重建容器必须是最后一动，重放补丁在其后**，重建后必跑 `python3 ~/.hermes/scripts/patch-sentinel.py` 到全绿才算收工。详见 [[replication/2-10Router-AI网关]]。

### tailscale 升级 SOP（0912 实测修正：二进制不在 GitHub Release，在官方包站）

```bash
# 本机形态：~/.local/bin/tailscaled 静态二进制（无 deb）；GitHub release 无 tgz 资产，真源是：
curl -sL -o /tmp/ts.tgz https://pkgs.tailscale.com/stable/tailscale_<版本>_amd64.tgz   # 文件名规律 tailscale_X.Y.Z_amd64.tgz
# 备份 → 替换（tailscale CLI 和 tailscaled 守护端一起换）→ 重启
cp ~/.local/bin/tailscaled ~/.local/bin/tailscaled.bak-<旧版本>
cp ~/.local/bin/tailscale  ~/.local/bin/tailscale.bak-<旧版本>
tar xzf /tmp/ts.tgz -C /tmp && install -m755 /tmp/tailscale_<版本>_amd64/tailscaled ~/.local/bin/tailscaled
install -m755 /tmp/tailscale_<版本>_amd64/tailscale ~/.local/bin/tailscale
sudo systemctl restart tailscaled   # 断连约 10 秒，自动重连
# 验证三连：tailscaled --version 新号 / sudo tailscale status 节点齐全 / curl https 走 8443 门 200
```

### sing-box 升级 SOP

```bash
# 本机形态：~/singbox/sing-box 二进制，root systemd 服务
# Releases 下载对应架构 zip → 备份 ~/singbox/sing-box → 替换 → systemctl restart sing-box
# 验证：curl -x http://127.0.0.1:7892 https://api.github.com 出网即通
```

### clone 组件升级 SOP（ai-token-dashboard）

```bash
cd ~/ai-token-dashboard
git -c http.proxy=http://127.0.0.1:7894 fetch --depth 1 origin main   # 走代理（ghfast 亦可）
git log --oneline HEAD..origin/main    # 先看差了什么再决定
# 有更新且想升：git merge origin/main && systemctl --user restart atd
```

### metacubexd 自动更新（低风险档，cron 执行体）

```bash
# 无卷无配置纯静态面板，坏了重拉即复原 → 允许自动
docker pull ghcr.io/metacubex/metacubexd:latest
docker stop metacubexd && docker rm metacubexd
docker run -d --name metacubexd --restart unless-stopped -p 9097:80 ghcr.io/metacubex/metacubexd:latest
curl -sf --max-time 10 http://127.0.0.1:9097 >/dev/null && echo OK || { 回滚旧镜像ID重run; 汇报; }
```

## 变更日志

| 日期 | 组件 | 动作 | 结果 |
|---|---|---|---|
| 2026-09-12 | — | 建卡：7 组件版本快照 + 三档 SOP + 巡检纪律拍板（周一核对/低风险自动/高风险点头） | ✓ |
| 2026-09-12 | Tailscale | 1.80.3→1.102.4（官方包站 tgz，CLI+守护端同换，备份 .bak-1.80.3） | ✅ 三连验证过（版本/节点/8443 门 200） |
| 2026-09-12 | Homarr | 08-05 镜像→09-12 新镜像（v1.77.1 代际）；先 docker cp 全量备份 /appdata，重建容器（原端口/卷/env-file）后塞回数据+restart | ✅ 迁移日志正常，DB 36 表数据完整（1 用户/1 面板/10 应用），浏览器直进面板会话未掉 |
| 2026-09-12 | AI Token大盘 | bfa2f24→3761176（+12 提交，含 Grok/DeepSeek-Harness/Pi 采集器与配额窗口修复）；stash 本地定制→ff merge→pop 解 1 冲突（上游已收编 pricing-custom 机制，死代码块 DEEPSEEK_OVERRIDES 删除） | ✅ node 语法过、服务重启 active、:8096 返回 200、15 文件本地定制保留未提交 |
| 2026-09-12 | — | **雷达扩编 v3**：+运行时三件套探针（AO/hermes-web-ui/hermes-agent 本体，npm/cnb 镜像渠道），监控面 7→10；值守 prompt 补三件套风险纪律；cron 更名「组件版本雷达巡检」。扩编即揪出 web-ui 落后 2 版、本体落后 10 提交（含 DeepSeek 窗口修复） | ✅ 脚本实测 10 项全报告出，误报清零 |
| 2026-09-12 | hermes-web-ui | 0.7.17→0.7.19（代理走 7894 npm 装新，sudo 重启服务） | ✅ :8648 出 200、标题正常、日志 startup complete + 会话 stats 读写=数据无恙 |
| 2026-09-12 | hermes-agent本体 | v0.21.1→v0.21.2（官方 `hermes update --backup --yes` 一条龙：快照+ff pull+依赖+config v33→v43+重启 gateway） | ✅ version 实锤、Lark wss 连接正常、归属句补丁面零回潮、上游两 remote 齐平；DeepSeek 1M 窗口修复已进 model_metadata.py |
| 2026-09-14 | — | 日检核对回填（无升级动作）：10Router 上游 v1.1.1（09-13 深夜发，落后1版）、hermes-web-ui 上游 0.7.21（09-12 连发 20/21，落后2版）、本体落后 557 提交（仍 0.21.2 版本内滚动，含 2 条 state.db 权限硬化）；哨兵手动体检 5 项指纹全绿；metacubexd 镜像 09-13 ≥ 上游 09-10 无需自动更新。三档建议见当日雷达报告 | 📋 等拍板 |
| 2026-09-16 | — | 二次复核拍板：确认升 3 项（AI Token大盘 / hermes-web-ui / 10Router），维持暂缓 2 项（sing-box 纯 fix 无安全通告、本体 1703 提交无急用项且默认最高危）。Homarr 0916 晨间 ❓ 复核实为 ghcr API 限流误报，镜像@09-12≥上游 v1.77.1(09-11) 真齐平 | ✅ 开工 |
| 2026-09-16 | AI Token大盘 | 79cd0c8→e5dbaf6（+7 提交：usage 记账/定价准确性修复+看板图表升级+依赖安全硬化）；stash→merge 解 2 冲突（styles.css 保留补丁03 并闭合上游媒体查询；hermes.mjs 本地调用级块对齐上游「会话×模型」复合键）+1 笔兼容 fix（title 列探测降级+HERMES_HOME 跟随）。120 测试全绿 | ✅ :8096 200、sessions 2457 行/841 带 title、调用级 events 25339 条 |
| 2026-09-16 | hermes-web-ui | 0.7.19→0.7.21（代理走 7894 npm 装新，sudo systemctl 重启系统级服务——注意：单元在 /etc/systemd/system 非 user 级） | ✅ :8648 200、startup complete、bridge 起、NRestarts=0 |
| 2026-09-16 | 10Router | v1.1.0→v1.1.1（pull 新镜像→rename 旧容器→同参数 run→重放 strict-proxy.cjs 3处 PATCHED→restart）。OAuth 钩子 NODE_OPTIONS 存活。数据对拍 49 连接/13 节点/3 池一致。旧容器删+悬空镜像回收 798MB，新镜像钉 `:1.1.1` 标签，`:1.1.0` 回滚标签 ghcr 仍在 | ✅ chat 实测 my-com1 出字、375 模型、哨兵 6 项全绿 |
| 2026-09-15 | — | 日检：4 项上游查询失败（sing-box/Homarr/metacubexd/大盘）经值守 agent 走 7894 代理重试全部查明——前三者实为齐平；**大盘 fetch 后实锤落后 6 提交**（usage 计费准确性修复+看板图表升级+依赖安全硬化，雷达 ❓ 漏报转 🔴）；本体落后扩至 846 提交（fix 为主，含 HEIF 图片解码、state.db 只读硬化）；哨兵 6 项指纹全绿；metacubexd 已齐平无需自动更新。无升级动作，建议清单见当日雷达报告 | 📋 等拍板 |
| 2026-09-16 | — | 日检：5 项落后（sing-box/10Router/大盘/web-ui/本体），Homarr ❓ 查明=GitHub API 对 7894 出口 IP 匿名限流误报，直连重试实为 v1.77.1 齐平；**已给雷达脚本 gh_get 加直连兜底腿（代理腿命中限流自动切直连），复跑 10 项 ❓ 清零**；哨兵 6 项指纹全绿；metacubexd 镜像 09-13≥上游 09-10 无需自动更新；本体落后扩至 1677 提交（未含 v2026.9.14 标签，fix 为主无急用项）。无升级动作，建议清单见当日雷达报告 | 📋 等拍板 |
| 2026-09-17 | — | 日检：❓ 仅 10Router 一项，走 7894 代理重试 200 查明=**假警报**（本地 1070a8836c3e=上游 v1.1.1，同镜像双标签，齐平）。**哨兵抓到 strictProxy 补丁丢失并已当场重放修复**：state.db 取证实锤=0916 升级会话当晚 20:29 收尾重建容器把白天重放的补丁冲掉（补丁打在容器层非卷，升级会话漏跑哨兵收尾）；重放 3 处 PATCHED→restart→dashboard 200→my-com1 出字实测（z-ai/glm-5.3）→哨兵 6 项全绿。落后 3 项复核：sing-box v1.14.1 仍纯 fix 无安全通告维持暂缓；web-ui 0.7.22（09-16 发，任务计划 MCP+MCP HTTP 别名配对修复+Bridge TCP 回退，有轻量实用项）；大盘 git fetch 实为齐平（雷达 🔴 误报，仅运行时数据文件本地改动）；本体落后 2122 提交（桌面端 revert 波+HERMES_HOME 安全硬化等，无当下急用项）。metacubexd 上游 v1.273.1(09-10)≤镜像@09-13 无需更新 | ✅ 补丁已修复+1 项待拍板 |
| 2026-09-17 | 10Router | strictProxy 补丁重放（哨兵报警→state.db 取证→docker cp+node 重放 3 处 PATCHED→restart→dashboard 200+chat 实测出字） | ✅ 哨兵 6 项全绿，根因=升级会话收尾重建冲容器层补丁，SOP 已补铁律 |

## 关联

- 部署形态详情：[[replication/DEPLOYMENT]] 及各编号指南（[[replication/1-网络出口与入口]] / [[replication/2-10Router-AI网关]] / [[replication/6-Homarr导航面板]]）
- 组件台账：[[02-Projects/10Router-网关系统|10Router-网关系统]] · [[02-Projects/家庭服务器基础设施架构与网络拓扑|家庭服务器基础设施架构与网络拓扑]]（02-Projects 各服务卡）
- 网络底座：[[家庭服务器网络拓扑与DNS解析]]


## 🔒 本地改动哨兵（patch-sentinel，0913 上线）

**背景**：上游每次升级/重构都可能冲掉本地外挂（0913 实锤：hermes update v0.21.2 重构网关文件名，fry-cards 全部 15 钩子被冲，飞书卡片退化纯文本大半天才发现）。升级动作和体检动作没焊在一起 = 有盲窗。

**机制**：`~/.hermes/scripts/patch-sentinel.py`
- **5 项指纹**：fry-cards 15 钩子、毒句修复（归属句=0）、10Router strictProxy、10Router OAuth 钩子 env、AO executor 补丁
- **触发**：手动运行（0913 老板拍板取消每小时定时巡检，系统 crontab 已删）。升级事件监听逻辑（hermes update 回执 + AO mtime 变化检测）仍内置在脚本，手动跑时自动生效
- **告警**：飞书裸 HTTP 直发 Home 群（tenant_token 自取，不依赖 Hermes/fry-cards 存活）+ stdout（cron 注入值守 agent）
- **只检不修**：修复动作由值守 agent/人工执行，报告带每项的重放命令
- **升级后全绿**也发一条低调"体检通过单"，证明闸门确实跑了

**升级 SOP 追加步骤**：任何 hermes update / 10Router 容器重建 / AO npm 升级之后 → 等哨兵下一跑（≤1h）或手动 `python3 ~/.hermes/scripts/patch-sentinel.py` → 有 ❌ 按"重放"命令逐项恢复+复跑哨兵到全绿。
