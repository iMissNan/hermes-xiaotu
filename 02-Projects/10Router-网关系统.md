---
title: 10Router 智能网关系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [ai, gateway, 10router, proxy]
aliases: [10Router, AI网关, 路由网关]
---

# 🌐 10Router 智能网关系统

> 💡 **核心定位**：家庭服务器的 AI 调度大脑，统一聚合上游各家 API、白嫖资源与本地模型，提供 OpenAI 兼容的统一出口与智能降级。

---

## 1. 核心访问入口与定位
- **局域网入口**：`http://<内网IP>:20128/`
- **公网/域名**：`http://<你的域名>:20128/`
- **部署类型**：Docker 容器（名称：`10router`）
- **认证凭据**：统一口令 `<统一口令>`，详见 [[03-Areas/账号与服务密码管理基线]]

## 2. 关键运行参数与架构
- **数据存储卷**：`~/.10router/data`
- **上游渠道**：
  1. Google Antigravity 原生渠道（绑定 7892 洛杉矶专用节点）；
  2. 南鲨白嫖签到渠道（TokenBom、ChatAI $50/日 等）；
  3. 通义千问/SiliconFlow 兜底链路；
- **组合链 (ComboChain)**：主模型降级链，首选高速免费，失败秒切兜底。

## 3. 极简运维指令
- 查看日志：`docker logs -f --tail 50 10router`
- 重启服务：`docker restart 10router`

## 4. 上下游拓扑关联
- 上游粮仓支持：[[02-Projects/TokenHub-代币资产管家]]
- 依赖网络出口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，确认与 TokenHub 的闭环联动。
