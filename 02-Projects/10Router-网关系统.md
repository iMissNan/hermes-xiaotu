---
title: 10Router 智能网关系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-23
tags: [ai, gateway, 10router, proxy]
aliases: [10Router, AI网关, 路由网关]
---

# 🌐 10Router 智能网关系统

> 🧩 从零复刻本服务：[[replication/2-10Router-AI网关]]

> 💡 **核心定位**：家庭服务器的 AI 调度大脑，统一聚合上游各家 API、白嫖资源与本地模型，提供 OpenAI 兼容的统一出口与智能降级。

## 1. 从零复刻部署指南

**上游项目**：[techysy/10router](https://github.com/techysy/10router)（MIT 协议，9Router 精简优化版；也可 `npm i -g @techysy/10router` 裸机跑，Docker 为推荐方式）。

### 1.1 Docker 部署（基础版，通用）

```bash
docker run -d --name 10router \
  --restart unless-stopped \
  -p 20128:20128 \
  -v ~/.10router:/app/data \
  -e PORT=20128 \
  -e DATA_DIR=/app/data \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -e KEEP_ALIVE_TIMEOUT=120000 \
  -e STREAM_FIRST_CHUNK_TIMEOUT_MS=90000 \
  -e STREAM_STALL_TIMEOUT_MS=150000 \
  ghcr.io/techysy/10router:latest
```

首次打开 `http://<内网IP>:20128/` 注册管理员账号，随后在面板内添加上游渠道与模型组合。

### 1.2 中国大陆网络增强（可选，按需取用）

Google 渠道（如 Antigravity）的 OAuth token 刷新走 `oauth2.googleapis.com`，CN 直连被墙会导致每小时 401 掉线。本仓 `assets/10router-patches/` 提供两个补丁：

- **google-oauth-proxy.cjs**：预加载钩子，仅拦截 Google OAuth 刷新请求并经 HTTP 代理隧道转发，其余流量原样放行，代理失败自动退回原生 fetch；
- **strict-proxy.cjs**：强制聊天链路 strictProxy（代理失败不回落裸连），镜像升级后按锚点自适应定位 chunk，幂等可重复执行。

```bash
# OAuth 代理补丁（放置 + env 挂钩）
mkdir -p ~/.10router/patches
cp assets/10router-patches/google-oauth-proxy.cjs ~/.10router/patches/
# 追加 env 后重建容器：
#   -e GOOGLE_TOKEN_PROXY=http://172.17.0.1:7892   （172.17.0.1 为 docker0 网关默认地址，端口换成你的 HTTP 代理）
#   -e NODE_OPTIONS=--require /app/data/patches/google-oauth-proxy.cjs

# strictProxy 补丁（进容器执行，一次性）
docker cp assets/10router-patches/strict-proxy.cjs 10router:/tmp/
docker exec 10router node /tmp/strict-proxy.cjs
docker restart 10router
```

### 1.3 升级与数据迁移

```bash
# 升级（数据卷持久化，直接拉新镜像重建）
docker pull ghcr.io/techysy/10router:latest
docker rm -f 10router   # 然后重跑 1.1 的 run 命令

# 备份/迁移 = 打包数据目录（SQLite 库 + 认证 + 密钥全在里面）
tar -czf 10router-data-$(date +%m%d).tar.gz -C ~ .10router/db .10router/auth .10router/jwt-secret
```

- 渠道、模型组合、密钥等全部配置存于 `~/.10router/db/data.sqlite`（SQLite WAL 模式）；跨机迁移还原该目录即得完整身份与配置。
- 升级若引入行为变化，`db/backups/` 内有自动快照可回退。

## 2. 本机运行台账（环境特定值以占位符书写）

- **入口**：局域网 `http://<内网IP>:20128/`；公网 `http://<你的域名>:20128/`
- **认证**：统一口令 `<统一口令>`，见 [[03-Areas/账号与服务密码管理基线]]
- **部署形态**（2026-09-23 升级）：**裸跑 node24 + ghcr 盒饭 app**（`/home/linxuan/apps/10router-bare-1.2.0`），数据目录权威统一为 `~/.10router-bare-data`（已清理退役旧目录 `~/.10router`），服务由 `systemd --user 10router.service`（`Restart=always` + 每分钟看门狗 + `Linger=yes`）全天候常驻守护。
- **出站代理与偏序契约**：官方 SQLite 持久化 `outboundProxyEnabled=true` + 65 项（846 字符）`outboundNoProxy` 全量白名单；启动参数严格满足 `连接 60s < 补丁推理 180s ≤ 首包 200s < 僵流 360s < 客户端 600s`。
- **补丁状态**：`google-oauth-proxy.cjs` 运行于 **rev7-passthrough** 观测版（流量交给官方 ProxyFetch），48h 观察期后择机退役 `--require`；历史死补丁与旧脚本已证死归档入 `_dead-archive/`。
- **上游渠道拓扑**：① Google Antigravity 原生渠道（支持 AES-256-GCM 凭据加解密）② StepFun 阶跃星辰四通道（国内/国际 × 按量/Step Plan）③ 国内直连通道（sensenova、AMD/SiliconFlow 毫秒级直连）；组合链首选高速免费、失败秒切兜底。

### 2.1 极简运维指令

```bash
systemctl --user status 10router.service   # 推荐守护状态查看
systemctl --user restart 10router.service  # 推荐平滑重启
curl --noproxy '*' http://127.0.0.1:20128/api/health  # 健康检查
tail -f /tmp/bare-20128.log               # 跟日志
```

## 3. 上下游拓扑关联

- 上游粮仓支持：[[02-Projects/TokenHub-代币资产管家]]
- 依赖网络出口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]
- 版本保鲜与升级 SOP：[[03-Areas/GitHub组件版本雷达|GitHub组件版本雷达]]
- 架构与研发哲学深度反推：[[01-Notes/10Router架构演进与研发工程实践规范]]


---
## 4. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，确认与 TokenHub 的闭环联动。
- `2026-09-12`：按公仓可复刻标准重写——补上游原址/Docker 部署/CN 网络增强补丁/升级迁移指南，补丁文件随仓发布（assets/10router-patches/）。
- `2026-09-20`：门牌对调 WO-B——裸跑 1.1.3（node24）接管 20128，7 处吃家零改动，断粮 40s；容器退役更名 `10router-old-20128`；升级 SOP 改「`docker pull` ghcr → `docker export` 解 app → `apply-armor.py` 重打护甲 → 临时口验 → 换目录重启」（分钟级）；作者小 commit 高频更新从此无痛。
- `2026-09-20`：装上游官方插件 **10router-sync v1.5.0**（zcode-plugin，commit 3a64974）——五源用量同步+实例状态监控+用量库体检清理，脚本直装进 `~/.hermes/skills/zcode-sync-10router/`（本机无 ZCode，走 AGENTS.md 非 ZCode 复用路径）。首同步 OpenCode 21 行幂等通过；status 零配置验活。体检发现 usageDaily 日桶祖传漂移（v108 备份即 mismatch，非新伤），如需对齐走 clean-usage-db 停服手术（待拍板）。
- `2026-09-20`：**全仓巡查补课**（老板指出装插件时未通读整仓）——全仓 clone 地毯式过了一遍：官方 11 个 agent 技能（中文版已本地存 ai-gateway-ops/references/10router-official-skills/）、cli 桌面/fnos 形态、`.env.example` 三个未用开关（SEARXNG/ALLOW_PRIVATE_HOSTS/API_KEY_ROTATION）、根 marketplace 仅一个插件。版本情报：**v1.1.4 代码已进仓但四官方通道（tag/npm/Release/ghcr）均未发版**，ghcr 1.1.3 digest `e3705c964c…` 与现役同串=零漂移；等作者发版（tag+Release 或 hasUpdate 翻真）即走 SOP 升级，升级通道 ghcr 镜像与 Release 的 server.tar.gz 二选一均可。资产地图已焊进 ai-gateway-ops 技能。
- `2026-09-23`：**WO-20260923 P2 系统性治理与 1.2.0 升级交付**——吸纳外部审计（WO-001/002）与去补丁化成果：① 清除 11 处退役目录（含旧 `~/.10router`）释放 ~800MB；② 修正 17 个运维脚本旧路径引用；③ 严守 WO-002 独立沙盒 SOP 预演验证；④ 护甲四锚点 100% 注入并补齐 standalone 依赖链；⑤ 1.2.0 整包无感平滑切换，原生 AES-256-GCM 凭据加解密对齐闭环，StepFun 四通道就绪；⑥ 详见 [[02-Projects/工单/WO-20260923-10Router-P2系统性治理与1.2.0升级]]。

