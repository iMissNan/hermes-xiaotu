---
title: 10Router 智能网关系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-12
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
- **部署形态**：Docker 容器（`10router`），数据卷 `~/.10router:/app/data`，重启策略 unless-stopped
- **已挂增强 env**：`GOOGLE_TOKEN_PROXY=<宿主HTTP代理地址>`、`NODE_OPTIONS=--require …/google-oauth-proxy.cjs`、流式首包/停滞超时 90s/150s
- **Tailscale 出口（可选挂载）**：容器内如需经 Tailscale 访问内网服务，另挂 `-v <tailscale二进制>:/usr/local/bin/tailscale -v /run/tailscale/tailscaled.sock:/var/run/tailscale/tailscaled.sock`
- **上游渠道拓扑**：① Google Antigravity 原生渠道（绑专用代理出口）② 南鲨白嫖签到渠道（TokenBom、ChatAI 等）③ 通义兜底链路；组合链首选高速免费、失败秒切兜底

### 2.1 极简运维指令

```bash
docker logs -f --tail 50 10router   # 跟日志
docker restart 10router             # 重启
docker stats 10router               # 资源占用
```

## 3. 上下游拓扑关联

- 上游粮仓支持：[[02-Projects/TokenHub-代币资产管家]]
- 依赖网络出口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 4. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，确认与 TokenHub 的闭环联动。
- `2026-09-12`：按公仓可复刻标准重写——补上游原址/Docker 部署/CN 网络增强补丁/升级迁移指南，补丁文件随仓发布（assets/10router-patches/）。
