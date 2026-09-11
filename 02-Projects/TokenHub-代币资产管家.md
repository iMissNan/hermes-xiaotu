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

> 💡 **核心定位**：“0元 AI 永动机”的粮仓管家，负责监控各第三方 API 站点的余额、白嫖签到状态、健康度，并向网关持续供血。

---

## 1. 核心访问入口与定位
- **局域网入口**：`http://<内网IP>:20129/`
- **公网/域名**：`http://<你的域名>:20129/`
- **部署类型**：Docker 容器（名称：`tokenhub`）
- **认证凭据**：统一口令 `<统一口令>`，详见 [[03-Areas/账号与服务密码管理基线]]

## 2. 关键运行参数与资产现状
- **持久化目录**：`/home/linxuan/.tokenhub`
- **签到自动化脚本**：`/home/linxuan/scripts/checkin-worker.sh`（Crontab 每日 00:05 及每 4 小时巡检）
- **已打通 4 大白嫖站**：
  1. `ChatAI`：每日白嫖 $50 额度；
  2. `ModelScope (魔搭)`：每日签到 +250 魔粒；
  3. `Apinex`：稳定签到连击；
  4. `TokenBom`：每日积分稳定入账。

## 3. 极简运维指令
- 查看日志：`docker logs -f --tail 50 tokenhub`
- 重启服务：`docker restart tokenhub`
- 手动测试签到：`bash /home/linxuan/scripts/checkin-worker.sh`

## 4. 上下游拓扑关联
- 下游消费方：[[02-Projects/10Router-网关系统]]
- 依赖网络出口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，完成浅色 10Router 风前端美化重构。
