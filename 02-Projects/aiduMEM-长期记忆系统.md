---
title: aiduMEM 长期记忆系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [ai, memory, aidumem, vector, sqlite]
aliases: [aiduMEM, 记忆系统, 长期记忆]
---

# 🧠 aiduMEM 长期记忆系统 (v20.4)

> 💡 **核心定位**：Hermes Agent 的原生第二大脑与跨会话事实中枢，支持自动蒸馏、向量化检索与实体知识图谱。

---

## 1. 核心访问入口与定位
- **Web 控制台**：`http://<你的域名>:8767/ui/`
- **健康检测接口**：`http://<你的域名>:8767/health`
- **部署类型**：Docker 容器（名称：`aidumem-v204`）
- **通信架构**：全离线架构，LLM 提炼对接 10Router，Embedding 走本地 `:8769`。

## 2. 核心架构与优化要点
- **数据卷持久化**：`~/data/aidumem`
- **提炼稳定性加固**：
  - 提炼超时放宽至 90 秒，避免长会话提炼断流；
  - 增加尾部 `[DONE]` 响应流正则净化，杜绝 JSON 解析报错。

## 3. 极简运维指令
- 查看健康状态：`curl -s http://127.0.0.1:8767/health | jq`
- 查看实时日志：`docker logs -f --tail 50 aidumem-v204`
- 重启容器：`docker restart aidumem-v204`

## 4. 上下游拓扑关联
- 依赖上游网关：[[02-Projects/10Router-网关系统]]
- 依赖宿主网络：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：完成 v20.4 升级与 90s 超时净化补丁，双推至 GitHub+Gitee。
