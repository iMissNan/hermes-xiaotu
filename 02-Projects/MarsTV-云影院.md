---
title: Mars TV 云影院系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [media, video, marstv, tvbox]
aliases: [Mars TV, 云影院, 影视站]
---

# 🎬 Mars TV 云影院系统

> 🧩 从零复刻本服务：[[replication/7-MarsTV云影院]]

> 💡 **核心定位**：家庭影音聚合站，提供“腾讯视频式”的海报墙、分类搜索、热播推荐与在线点开即播。

---

## 1. 核心访问入口与定位
- **局域网/公网入口**：`http://<你的域名>:8082/`
- **影视仓/TVBox 蜘蛛接口**：`http://<你的域名>:8090/`
- **服务根目录**：`/opt/martv`
- **部署类型**：Host 原生 Python/Node 服务（由 systemd 托管）

## 2. 核心架构与维护要点
- **双方案并行**：
  1. 手机/电视端：使用影视仓 App 挂载 TVBox 蜘蛛接口；
  2. 电脑端：浏览器直接访问 8082 云影院海报墙；
- **定时片库巡检**：Crontab 定时增量更新片源，失效源自动剔除，保障点开即播。

## 3. 极简运维指令
- 查看状态：`systemctl --user status martv`
- 重启服务：`systemctl --user restart martv`

## 4. 上下游拓扑关联
- 统一网络入口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：初始化资产主卡，确认与 Homarr 导航探针全面接通。
