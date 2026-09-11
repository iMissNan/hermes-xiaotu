---
title: aiduMEM 全离线记忆引擎部署与排障 SOP
category: notes
status: active
updated: 2026-09-11
tags: [aidumem, memory, embedding, bge, sqlite]
---

# 🧠 aiduMEM 全离线记忆引擎部署与排障 SOP

> **摘要**：记录 aiduMEM v20.4 在家庭服务器 HP 主机上的全离线化部署规范、架构拓扑、底层避坑经验与数据备份还原准则。

---

## 1. 全离线架构与服务拓扑

```
[Hermes Agent] 
       │ (MemoryProvider 交互)
       ▼
[aiduMEM v20.4] (:8767 / Systemd: aiduMEM.service)
       ├── 向量存储 ──> 本地 SQLite 向量库 (~/.hermes/aidumem-v204/data/)
       ├── 结构化图谱 ─> facts.db (实体、双链与关系表)
       ├── 嵌入计算 ──> 本地 Embedding-Server (:8769, bge-base-zh-v1.5)
       └── 提取与演化 ─> 10Router 网关 (:20128) 调度大模型处理
```

- **全离线原则**：向量嵌入完全收拢在本地端口 `:8769`，不再外发云端 API，消除网络延迟并确保极度隐私；
- **Rerank 策略**：2026-09 决策——停用外部重排器，简化推理调用链，提升端到端召回吞吐。

---

## 2. 关键避坑实录与研发铁律

### (1) “全量”语境的唯一含义
- **铁律**：按官方文档全量安装、全功能开启、一次到位；**严禁自行推测阉割功能**或采取挤牙膏式试探升级；升级前必通读官方 Release 文档。

### (2) Obsidian 双链图谱与 facts 表关联断点
- **排障复盘**：早期双链节点在前端 StarMap 显示“未连接”，根因是 `routes_obsidian.py` 仅将双链词写入了 `entities`，未在 `facts` 与 `fact_entities` 创建关联行，导致前端查询时的 `INNER JOIN` 链返回空集；
- **当前定稿**：已实施代码级补丁，同步笔记时自动生成 `source='obsidian'` 事实记录并绑定实体关系。

### (3) <CPU型号> 无 AVX2 指令集限制
- **硬件制约**：奔腾 <CPU型号> 处理器不支持 AVX2；
- **编译要求**：涉及 Go / C++ 预编译的外部扩展（如某些向量库或特定工具），必须选择 `v1` 或 `v2` 兼容版本架构，严禁拉取带 AVX2 优化的二进制。

---

## 3. 日常健康巡检与备份命令

```bash
# 检查健康探针与存活性
/home/linxuan/.hermes/scripts/aidumem-curl.sh GET /health | jq .

# 检查当前记忆与实体总数
/home/linxuan/.hermes/scripts/aidumem-curl.sh GET /stats | jq .

# 备份数据库文件（位于 ~/backups/ 统一归档池）
cp ~/.hermes/aidumem-v204/data/facts.db ~/backups/facts-backup-$(date +%Y%m%d).db
```

---

## 🔗 关联索引
- 上级主索引：[[Home|知识库主索引]]
- 服务定稿卡：[[02-Projects/aiduMEM-长期记忆系统|aiduMEM 长期记忆系统]]
- 知识治理：[[03-Areas/Obsidian知识库-5W1H自动化治理规范|Obsidian 知识库 5W1H 自动化治理规范]]
