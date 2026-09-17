---
title: Hello-Agents 智能体教程知识地图（datawhalechina/hello-agents）
category: reference
status: active
updated: 2026-09-17
tags: [agent, llm, rag, mcp, 教程, datawhale, 知识地图]
source: https://github.com/datawhalechina/hello-agents
---

# Hello-Agents 智能体教程知识地图

> 📌 **一句话定位**：Datawhale 社区开源的《从零开始构建智能体》系统教程，中文圈 Agent 学习的顶流仓库（⭐ 79,463 / 🍴 9,874，2025-09-07 创建）。理论到实战全链路：从 LLM 基础 → 自研 Agent 框架 → 记忆/RAG/上下文工程/MCP 协议 → Agentic RL 训练 → 三个综合项目。

## 5W1H 速览

| 维度 | 内容 |
|---|---|
| What | Datawhale 系统性 Agent 教程 + 配套代码 + 自研框架 HelloAgents |
| Why | 穿透框架（Dify/Coze/LangChain）表象，理解 AI Native Agent 核心原理；后续遇到 Agent 设计问题可在此查方法论与实现范式 |
| Who | Datawhale 社区（开源协作），核心贡献者 jjyaoao 等；框架仓库 github.com/jjyaoao/helloagents |
| When | 仓库创建 2025-09-07；本地扫描快照 commit `4f7682c`（2026-09-04） |
| Where | 主仓 github.com/datawhalechina/hello-agents；在线阅读 datawhalechina.github.io/hello-agents/（国外）/ hello-agents.datawhale.cc（国内加速）；PDF 版见 README 下载区 |
| How | 在线读 or `git clone --depth 1`（全量约 340M，含图片）；代码在 `code/chapterN/`，章节正文在 `docs/chapterN/`（中英双语各一份） |

## 📖 章节地图（16 章 · 五大板块）

### 第一部分：智能体与语言模型基础（第 1–3 章）
- **第 1 章 初识智能体**：智能体定义、类型（单/多模态）、感知-行动循环、5 分钟实现第一个智能体
- **第 2 章 智能体发展史**：符号主义（专家系统/SHRDLU）→ ELIZA → 明斯基心智社会 → LLM 驱动新范式
- **第 3 章 大语言模型基础**：Transformer/Decoder-Only、提示工程、分词、缩放法则与局限

### 第二部分：构建你的 LLM 智能体（第 4–7 章）
- **第 4 章 经典范式构建**：⭐ 手写 ReAct、Plan-and-Solve、Reflection 三大范式（含工具定义、调试技巧）——查"Agent 循环怎么写"看这章
- **第 5 章 低代码平台**：Coze、Dify、n8n 实操（"每日 AI 简报"助手案例）
- **第 6 章 框架开发实践**：AutoGen、AgentScope、LangGraph、CAMEL 对比与实战——查"框架选型"看这章
- **第 7 章 构建你的 Agent 框架**：⭐ 用 OpenAI 原生 API 从零自研 HelloAgents 框架（多提供商支持、本地模型、Message 类、自动检测）——理解框架内部机制看这章

### 第三部分：高级知识扩展（第 8–12 章）⭐ 与本家体系关联最紧
- **第 8 章 记忆与检索**：认知科学启发的记忆系统设计、MemoryTool/MemoryManager、RAG 全流程（嵌入/检索/生成）——对照本家 aiduMEM 双链记忆体系阅读，互为印证
- **第 9 章 上下文工程**：ContextBuilder、GSSC 流水线、长时程任务上下文管理——对照 Hermes 上下文压缩机制
- **第 10 章 智能体通信协议**：⭐ MCP（传输方式/客户端/社区生态）、A2A、ANP 三协议对比——对照本家 Hermes MCP 接入实践
- **第 11 章 Agentic-RL**：从 SFT 到 GRPO 训练实战（GSM8K 数据集、奖励函数设计、训练全流程）——训练侧知识，本家暂无对应设施，纯理论储备
- **第 12 章 智能体性能评估**：BFCL 工具调用评测、核心指标、评估框架——对照本家 free-model-benchmark 技能的测评选型

### 第四部分：综合案例进阶（第 13–15 章）
- **第 13 章 智能旅行助手**：MCP + 多智能体协作真实项目（Pydantic 数据模型、Web 应用、5 分钟跑通）
- **第 14 章 自动化深度研究智能体**：DeepResearch Agent 复现（TODO 驱动研究范式、三阶段流程）——对照本家 web_search/exa 检索链路
- **第 15 章 构建赛博小镇**：AI Town（NPC Agent、记忆系统集成、好感度系统、批量对话生成）

### 第五部分：毕业设计（第 16 章）
- 完整多智能体应用从设计到交付的方法论

## 📎 附加内容

- **Extra-Chapter（13 篇）**：面试问题总结、上下文工程补充、Dify 保姆级教程、AgentSkills 解读、GUI Agent/WebAgent 科普实战、如何写出好 Skill、Agent 自进化、开发踩坑经验、旅行助手后训练实战
- **Additional-Chapter**：N8N 安装指南、NodeJS 安装指南
- **Co-creation-projects（48 个）**：学员共创项目集（数据分析、股票洞察、代码审查、SRE 值班、邮件助手、小说生成、健康档案等）——找同类项目灵感/参考实现时翻这里
- **code/ 目录**：每章配套代码，749 个 .py + 27 个 .ipynb；第 6 章含 AutoGen/AgentScope/LangGraph/CAMEL 四套 Demo；第 10 章含 weather-mcp-server 示例；13–15 章为完整项目（trip-planner / deepresearch / AI-Town）

## 🔗 与本家体系的取用对照表

| 本家需求/场景 | 去 Hello-Agents 哪里查 |
|---|---|
| Agent 循环/范式设计（ReAct 等） | 第 4 章 + code/chapter4 |
| 记忆系统设计、RAG 流程原理 | 第 8 章（对照 aiduMEM） |
| 上下文窗口管理、长任务上下文 | 第 9 章（对照 Hermes 压缩机制） |
| MCP 协议接入、传输方式疑问 | 第 10 章 + code/chapter10/weather-mcp-server |
| 模型评估/基准测试选型 | 第 12 章（对照 free-model-benchmark） |
| 多智能体编排实战参考 | 第 13 章旅行助手、AO 工作流对照 |
| 写 Skill/提示词方法论 | Extra05/Extra08 |
| 智能体面试题、概念查漏 | Extra01 面试问题总结 |
| 同类项目实现参考 | Co-creation-projects/ 48 项目 |

## 取用方式

- **快速查**：直接问小兔，本知识地图 + aiduMEM 记忆可秒答章节归属
- **深读**：在线阅读 https://hello-agents.datawhale.cc 或本地 `git clone --depth 1 https://github.com/datawhalechina/hello-agents`（扫描用临时目录已清理，随用随拉）
- **单章直取**：`docs/chapterN/第N章 *.md`（中文版）；框架源码 jjyaoao/helloagents

---
*快照信息：扫描于 2026-09-17，commit 4f7682c（2026-09-04），当时 79,463 stars。仓库持续更新中，章节可能增补，深读前建议 `git pull`。*
