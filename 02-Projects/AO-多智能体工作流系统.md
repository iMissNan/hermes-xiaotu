---
title: AO 多智能体工作流系统
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [ai, agent, workflow, orchestrator, ao]
aliases: [AO, agency-orchestrator, AO流水线]
---

# 🏗️ AO 多智能体工作流系统

> 🧩 从零复刻本服务：[[replication/12-AO多智能体工作流]]

> 💡 **核心定位**：把大任务画成图纸，交给多个 AI 专家（后端/前端/QA/审计）在流水线上接力干。每个专家干完一步就"举手汇报"，独立验收员用更强的模型把关——淘汰"打一下走一步、漏洞全靠人肉抓"的老模式。

---

## 1. 核心访问入口与定位
- **安装位置**：`~/.npm-global/lib/node_modules/agency-orchestrator/`（ao 0.19.2）
- **运行大盘**：`http://<你的域名>:20132/`（看产出、步骤档案、耗时）
- **举手汇报面板**：`http://<你的域名>:20133/`（每步专家干完自动汇报，只读独立库）
- **启动纪律**：必须用 `~/.local/bin/ao-run-safe` 带 `--session-id` 启动，**禁止裸跑 `ao run`**
- **工作流图纸**：`~/.hermes/workspace/workflows/`（YAML，写明角色/验收标准/模型）
- **运行产物**：`~/.hermes/workspace/ao-output/`（目录名=完成时刻 UTC 时间，不是启动时间）

## 2. 模型分工与验收防线
- **实施**用 yangmao（耐磨免费）；**验收员/红队/审计**用 Antigravity（强，YAML 顶层 `verify_llm` 独立配置）
- **主动扫描验收**（补丁 5）：验收员不只按字面判，主动扫四类高危缺陷——空值、并发、边界、契约不匹配；抓到即判失败并自动返工
- **大任务模型选择**：架构/验收用 Antigravity，实施用 yangmao（2026-09 分级规范）

## 3. 汇报链路（2026-09-11 大修版）
- 专家每步干完 → 引擎钩子（executor.js 补丁 6）→ `~/.local/bin/hermes-handover` v3 → **独立 sidecar 库** `~/.hermes/handover.db` → 面板 ：20133 展示
- 状态如实映射：completed→✅ / skipped→⏭️ / error→❌；**未上报状态不构成验收结论**（杜绝"跳过的步骤也报全部通过"）
- **主会话库 state.db 零外部写入**（旧版直写 state.db 冒充 AI 汇报的手术已彻底改造）

## 4. 关键文件与维护
| 文件 | 作用 |
|---|---|
| `~/.local/bin/ao-run-safe` | 唯一启动入口（V4.1：时长预估横幅 + 看门狗登记） |
| `~/.local/bin/hermes-handover` | 举手汇报写入器（v3 sidecar 版） |
| `~/.local/bin/handover-board.py` | :20133 面板（systemd 自愈 `ao-handover-board.service`） |
| `~/.local/bin/ao-verify-patch.sh` | 主动扫描验收补丁（幂等，升级 ao 后重打） |
| `~/.hermes/handover.db` | 汇报 sidecar 库（独立于主库） |

- **补丁台账**（1-6 号）全部登记在 `~/.hermes/skills/autonomous-ai-agents/ao-workflow-engineering/SKILL.md`——**升级 ao 后按台账重打补丁**
- **历史教训**：改引擎必须先备份+登记（2026-09-11 有会话零备份动手术、25 条假"✅"汇报混进会话库，已审计定案）；AI 自称"已修复"一律要原文证据
- 配套方法论：[[01-Notes/多智能体工作流设计规格]]（验收模板/防模型劫持/择路规则）

## 5. 上下游拓扑关联
- 模型供血：[[02-Projects/10Router-网关系统]]
- 业务服务：[[02-Projects/TokenHub-代币资产管家]]（tokenhub-v3 升级由 AO 流水线完成）
- 基础网络：[[02-Projects/家庭服务器基础设施架构与网络拓扑]]

---
## 6. 变更历史（原位追加）
- `2026-09-11`：建主卡。AO 强化全套上线：主动扫描补丁 v2、verify_llm 独立验收、举手汇报 v3（sidecar 隔离）、:20133 面板、时长预估横幅；同日审计定案旧会话非法手术（详见技能台账补丁 6）。
