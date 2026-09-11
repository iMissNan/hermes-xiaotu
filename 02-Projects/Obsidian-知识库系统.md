---
title: Obsidian 知识库系统 (Web)
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [notes, obsidian, pkm, second-brain]
aliases: [Obsidian, 知识库系统, 第二大脑]
---

# 📚 Obsidian 知识库系统 (Web)

> 💡 **核心定位**：家庭服务器的第二大脑中枢，基于 LinuxServer Obsidian 容器的 WebRTC/WebSocket 像素流式桌面，兼具印象笔记式的高效浏览与本地 Markdown 资产沉淀。

---

## 1. 核心访问入口与定位
- **HTTPS 安全入口 (推荐)**：`https://<你的域名>:8084/`
- **HTTP 基础端口**：`http://<你的域名>:8083/`（因浏览器安全上下文限制，仅供内部调试）
- **部署类型**：Docker 容器（名称：`obsidian-web`）
- **认证凭据**：统一口令 `<统一口令>`，详见 [[03-Areas/账号与服务密码管理基线]]

## 2. 关键运行参数与架构
- **笔记物理目录**：`~/data/obsidian-vault`（挂载至容器内 `/vaults/obsidian-vault`）
- **配置文件持久化**：`~/.local/opt/obsidian-web/config`
- **SSL 证书挂载**：挂载宿主 Let's Encrypt 证书至 `/config/ssl/`，保障 WebCodecs 硬件加速正常唤醒。

## 3. 极简运维指令
- 重启容器：`docker restart obsidian-web`
- 检查桌面进程：`docker exec obsidian-web ps aux`
- 查看 Web 串流日志：`docker logs -f --tail 50 obsidian-web`

## 4. 上下游拓扑关联
- 知识库治理规范：[[03-Areas/Obsidian知识库-5W1H自动化治理规范]]
- 排障踩坑经验：[[01-Notes/WebCodecs与HTTPS安全上下文排障实录]]
- 统一网络入口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：解决黑屏与无头浏览器鉴权问题，换装 HTTPS 8084 正规证书并实现开机秒开知识库。
