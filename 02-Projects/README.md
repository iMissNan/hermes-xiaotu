---
title: 02-Projects 核心服务资产规范
category: guide
status: active
updated: 2026-09-11
---

# 🚀 02-Projects (核心自托管服务资产主卡)

此目录存放服务器上每一个运行中系统/容器的**唯一定稿档案**。

## 规则与生命周期
1. **一服务一卡片**：严格遵循单例原则。每个服务（如 10Router、TokenHub）全库只有唯一一张 Markdown 主卡；
2. **原位更新 (Update-in-Place)**：修改端口、路径、版本或依赖时，直接就地修改原文件，末尾追加变更流水；
3. **随生随灭**：服务运行中，卡片标记 `status: active`；若容器销毁下线，整体流转至 `04-Archives/`，绝不在活跃区遗留僵尸卡片。
