---
title: WebCodecs 与 HTTPS 安全上下文排障实录
category: note
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [webrtc, webcodecs, ssl, nginx, homarr, troubleshooting]
aliases: [Obsidian黑屏排查, WebCodecs安全上下文]
---

# 🛠️ WebCodecs 与 HTTPS 安全上下文排障实录

> 💡 **核心问题**：自托管 Web 桌面（如 LinuxServer 系列的 Obsidian-web、Kasm、Selkies）在局域网通过普通 HTTP 打开时，为什么会永久黑屏？

---

## 1. 故障现象
从局域网其他电脑访问 `http://<内网IP>:8083` 时，浏览器页面呈现整片黑屏，无法进入 Obsidian 操作界面；同时在 Homarr 导航面板上，状态指示灯长年报红点。

## 2. 深度根因分析 (Root Cause)
1. **WebCodecs 硬件加速死锁**：
   - 现阶段 LinuxServer 容器化 GUI 广泛采用 Selkies 串流技术，通过浏览器的 `VideoDecoder`（WebCodecs API）实时解码远程桌面画面；
   - W3C 标准强制规定：**非 `localhost` 的非安全上下文（即纯 HTTP 访问）将完全禁用 WebCodecs**；
   - 浏览器控制台抛出铁证错误：`FATAL: Not in a secure context. WebCodecs require HTTPS.`。直接导致视频解码管道拒绝初始化，前端画面卡死在初始黑屏。
2. **知识库未默认挂载**：
   - 第一次启动容器时，Obsidian 未加载任何 Vault，停留在初始化欢迎创建界面；
3. **Homarr 探针回环死循环**：
   - 容器内 Homarr 探测 `127.0.0.1:8083` 会指向 Homarr 容器本身，导致误判离线报红。

## 3. 标准解决方案
1. **换装合法 HTTPS 证书**：
   - 将服务器上已由 Let's Encrypt 签发的正规域名证书挂载至容器的 `/config/ssl/` 目录；
   - 对外暴露 HTTPS 安全端口（如 `8084`）；
2. **预注入知识库配置文件**：
   - 在 `/config/.config/obsidian/obsidian.json` 中预置 `vaults` 路径为 `/vaults/obsidian-vault`，并将 `open: true`；
3. **Homarr 探针修正**：
   - 探针地址修正为内网/公网域名或宿主 IP，彻底恢复绿灯健康。

## 4. 关联资产
- 宿主系统主卡：[[02-Projects/Obsidian-知识库系统]]
- 网络统一入口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史
- `2026-09-11`：总结自 2026-09-11 凌晨针对 Obsidian Web 端黑屏的真实排障过程。
