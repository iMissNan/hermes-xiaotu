---
title: AI 出口网络代理与 Sing-box 分流策略
category: notes
status: active
updated: 2026-09-11
tags: [proxy, sing-box, 10router, network, ai-infra]
---

# 🌐 AI 出口网络代理与 Sing-box 分流策略

> **摘要**：记录家庭服务器针对海外大模型（Google Gemini、Antigravity、OpenAI 等）构建的高稳定、防封控、防流量烧毁的多层分流与自愈架构。

---

## 1. 核心架构与端口拓扑

```
[家庭服务器业务] 
  ├── 10Router 网关 (:20128) ──────┐
  ├── Antigravity 客户端 ──────────┤
  └── 通用工具/爬虫 ───────────────┼──> sing-box 分流中枢 (:7892 / :7894)
                                    │     ├── Google/AG 专用通道 ──> UCloud 洛杉矶原生节点 (la-guard)
                                    │     ├── 通用外网/媒体 ──────> 机场订阅池 (ut-ai, 2yuan)
                                    │     └── 流量监控告警 ───────> 600G 月度熔断保护
```

- **端口 7892**：sing-box 混合代理端口（主通道，走 UCloud 优质出口）；
- **端口 7894**：兜底分流通道（走 2yuan 机场订阅）；
- **metacubexd (:9097)**：WebUI 节点状态与延迟观测面板。

---

## 2. 核心避坑与风控铁律

### (1) Google / Antigravity 429 风控与品牌冒充根因
- **现象**：请求 Gemini 频繁报 429 或配额耗尽，但后台实际配额充足。
- **真因分析**：Google 服务端对非原生出口 IP 以及特定客户端标识存在严格冒充风控。
  - **毒句排查**：提示词首句包含 `created by Nous Research` 会直接触发 Google 规则拦截；
  - **解决方案**：在 `SOUL.md` 与 prompt builder 中剔除敏感归属句，保留 Hermes Agent 纯净身份；
  - **冷却机制**：测试 AG 间隔必须 $\ge 150\text{s}$，防止本地客户端锁触发假性 429。

### (2) UCloud 洛杉矶 600G 流量熔断保护
- **铁律**：UCloud 洛杉矶 VPS 首年 ¥90，每月限额 600GB。**严禁 YouTube 等通用大流量走 UCloud**！
- **分流机制**：
  - Google / AG / 核心 API 走 `la-guard`；
  - YouTube、流媒体与通用 Web 爬虫强行分流至机场订阅 (`ut-ai`)；
  - 配套自动化脚本 `la-traffic-monitor.py`：每 5 分钟采样流量，达到 98% 自动熔断切换，月初 1-3 号自动恢复。

---

## 3. 极简运维与排障命令

```bash
# 查看 sing-box 服务状态
systemctl status sing-box.service

# 手动触发订阅节点健康检测与故障自愈
python3 ~/.hermes/workspace/scripts/singbox-sub.py failover

# 检查当前出海出口公网 IP
curl -x http://127.0.0.1:7892 https://api.ipify.org
```

---

## 🔗 关联索引
- 上级主索引：[[Home|知识库主索引]]
- 依赖服务卡：[[02-Projects/10Router-网关系统|10Router 智能网关系统]]
- 凭据基线：[[03-Areas/账号与服务密码管理基线|账号与服务密码管理基线]]
