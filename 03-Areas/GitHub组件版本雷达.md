---
created: 2026-09-12
updated: 2026-09-12
tags: [区域, 运维, 版本管理]
type: area
status: evergreen
---

# GitHub 组件版本雷达

> 管辖域：本机所有"真·GitHub 血统"组件的版本保鲜。目标：**上游大版本迭代了，我们不能还踩着有 bug 的旧版本**。
> 分工：本卡 = 台账 + 更新 SOP；智能巡检 = Hermes cron「GitHub组件版本雷达巡检」（每日 03:30，脚本报告 + agent 分析）；升级动作 = metacubexd 可自主（失败自回滚），其余经权限所有者点头后 agent 执行。

## 巡检与更新纪律（拍板于 2026-09-12，同日升级：周检→每日凌晨+agent 思考）

- **每日 03:30 智能巡检**（cron `b8b613f4ece2`，agent 模式）：脚本 `~/.hermes/scripts/version-radar.py` 先出客观日检报告（只呈现差距不动手），注入值守 agent → **agent 分析决策**：查上游 release notes 判断值不值（安全/bug 修复 vs 纯功能），评估「升级后会不会没法用」（补丁兼容性/数据备份/网络命脉断连），全齐平时只回一行不刷屏。
- **唯一可自主升级项**：metacubexd（无卷无配置纯静态面板）——pull→recreate→验证 9097，失败即用旧镜像 ID 自动回滚。
- **其余全部只给建议**：agent 报「建议升/暂缓/不推荐」+理由+回滚路径，**权限所有者点头才动手**；建议升的判定尤其看补丁锚点是否对新版本仍适用（10Router CN 补丁）、sqlite 是否已备份（Homarr）。
- 每次升级后回填本卡「版本快照」表 + 记一行变更日志（改文件即可，git 提交仍须权限所有者点头）。

## 版本快照（巡检回填，最近核对：2026-09-12）

| 组件 | 血统形态 | 本地 | 上游 | 差距 | 档位 | 详情/升级方法 |
|---|---|---|---|---|---|---|
| Tailscale | Releases 二进制 | **1.102.4** ✅0912升 | v1.102.4 | ✅ 齐平 | 手动 | [[#tailscale 升级 SOP]]（回滚锚点 `tailscaled.bak-1.80.3`） |
| Homarr | ghcr 镜像 | 镜像@2026-09-12 ✅0912升 | v1.77.1 (09-11) | ✅ 已追平 | 手动（有 sqlite+卷） | [[#ghcr 容器升级 SOP]]（db 备份 `~/homarr-appdata-backup-0912`） |
| metacubexd | ghcr 镜像 | 镜像@2026-09-12 | v1.273.1+ (09-10后) | ✅ 已自动更新 | **自动** | [[#metacubexd 自动更新]] |
| ai-token-dashboard | git clone（ghfast 加速） | **3761176** ✅0912升 | HEAD 3761176 (09-08) | ✅ 齐平 | 手动 | [[#clone 组件升级 SOP]]（本地定制15文件保留未提交；锚点 `.bak-0912`+`.patch`） |
| 10Router | ghcr 镜像 | 1.1.0 (rev 2205ba19) | v1.1.0 (09-11) | ✅ 齐平 | 手动（带补丁+db） | [[#ghcr 容器升级 SOP]] |
| sing-box | Releases 二进制 | 1.14.0 | v1.14.0 (08-31) | ✅ 齐平 | 手动（网络命脉） | [[#sing-box 升级 SOP]] |
| simplehub | ghcr 镜像 | 容器已停用 | v1.0.2 | ⚪ 被裸机 TokenHub 替代 | 不跟 | 留档 |

> 上游数据来自 GitHub API `releases/latest`；ghcr 镜像无版本标签时以镜像构建日期（`docker inspect .Created`）为锚。

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
- **10Router 实况参数**：`20128:20128`，卷 `~/.10router:/app/data` + tailscale bind×2，env 含 `NODE_OPTIONS=--require /app/data/patches/google-oauth-proxy.cjs`（CN 补丁在数据卷里，升级镜像不动补丁，但**大版本后要抽查 Google OAuth 刷新是否仍走代理**）。详见 [[replication/2-10Router-AI网关]]。

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

## 关联

- 部署形态详情：[[replication/DEPLOYMENT]] 及各编号指南（[[replication/1-网络出口与入口]] / [[replication/2-10Router-AI网关]] / [[replication/6-Homarr导航面板]]）
- 组件台账：[[02-Projects/10Router-网关系统|10Router-网关系统]] · [[02-Projects/家庭服务器基础设施架构与网络拓扑|家庭服务器基础设施架构与网络拓扑]]（02-Projects 各服务卡）
- 网络底座：[[家庭服务器网络拓扑与DNS解析]]
