---
title: TokenHub 代币资产管家
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [ai, tokens, checkin, tokenhub]
aliases: [TokenHub, 粮仓管家, 代币看板]
---

# 💰 TokenHub 代币资产管家

> 🧩 从零复刻本服务：[[replication/9-TokenHub]]

> 💡 **核心定位**：“0元 AI 永动机”的粮仓管家，负责监控各第三方 API 站点的余额、白嫖签到状态、健康度，并向网关持续供血。

---

## 1. 核心访问入口与定位
- **局域网入口**：`http://<内网IP>:20129/`
- **公网/域名**：`http://<你的域名>:20129/`
- **部署类型**：Systemd 系统级服务 (`tokenhub.service`，全原生 Node.js + SQLite)
- **部署目录**：`/opt/tokenhub/` (已彻底抛弃旧 Docker SimpleHub 镜像与外挂猴子补丁)
- **认证凭据**：统一口令 `<统一口令>`，凭据统一由 Vaultwarden 代管，详见 [[03-Areas/账号与服务密码管理基线]]

## 2. 关键运行参数与资产现状
- **持久化目录**：`/opt/tokenhub/data/tokenhub.db`
- **极简总控脚本**：`bash /opt/tokenhub/tokenhub.sh {status|restart|test|backup}`
- **防封单锁机制**：内置 14h 排他单锁，严格防止并发与重复打卡封号
- **已打通 4 大白嫖采粮站 + 14 备用直连站**：
  1. `ChatAI`：每日白嫖 $50 额度 (Codex 纯 HTTP 免封)；
  2. `ModelScope (魔搭)`：每日签到 +250 魔粒；
  3. `Apinex`：稳定签到连击 +100,000 T；
  4. `TokenBom`：TOTP 自动化积分入账。
- **10Router 热拔插**：原生直通 `:20128`，246 个模型在线，死站欠费秒级自动隔离。

## 3. 极简运维指令
- 查看状态：`bash /opt/tokenhub/tokenhub.sh status`
- 查看日志：`bash /opt/tokenhub/tokenhub.sh logs`
- 重启服务：`bash /opt/tokenhub/tokenhub.sh restart`
- 手动测试采粮：`bash /opt/tokenhub/tokenhub.sh test`
- 手动触发冷备：`bash /opt/tokenhub/tokenhub.sh backup`

## 4. 上下游拓扑关联
- 下游消费方：[[02-Projects/10Router-网关系统]]
- 实施载体：v3 升级由 AO 多智能体流水线完成，详见 [[02-Projects/AO-多智能体工作流系统]]
- 依赖网络出口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，完成浅色 10Router 风前端美化重构。
- `2026-09-11`：收录现代前沿设计灵感库：https://app.viainti.com/ (Viainti)，作为 UI/UX 深度重构与新颖视觉的参考标准。
- `2026-09-11`：v3 升级经 AO 多智能体流水线完成（数据引擎/前端工作台/QA 三步 + Antigravity 独立验收）；产物经大盘审计确认真实落盘。
