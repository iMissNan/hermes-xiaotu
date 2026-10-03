# free-model-radar（免费模型雷达）系统规格设计书

> 日期：2026-10-01  
> 状态：Grill Me 追问共识定案（1A, 2B, 3A, 4A, 5A）  
> 目标：实现 10Router 免费模型的常态化自动巡检、按规探查、审批换血，达成「常用、能用、好用、一直用」。

---

## 一、 系统定位与演进

- **名称**：`free-model-radar`（免费模型雷达），由原 `free-model-benchmark` 迭代演进。
- **核心宗旨**：变“被动单次盲打”为“主动常态巡检”；官方写清规格的按规则核验，官方未注明的用五维探针硬撬上限；以最小 Token 损耗保障 10Router 免费模型池健康与自愈。

---

## 二、 架构与模块划分

```
free-model-radar/
├── SKILL.md                  # 技能正本与操作指引
├── config/
│   └── vendors.yaml          # 供应商花名册（官网文档、活动目录、API 端点、凭据引用）
├── data/
│   └── model-radar.sqlite    # 独立数据库（当前态 + 30 天流水）
├── scripts/
│   ├── run.py                # 主控制入口（CLI 调度、模式分流）
│   ├── crawler.py            # 官网与活动页轻量嗅探器（API 模型比对 + llms.txt/events diff）
│   ├── probe_engine.py       # 两级测试引擎（L1 极轻心跳 / L2 规约校准+五维深测）
│   ├── router_advisor.py     # 10Router 对齐与 diff 建议生成器
│   └── feishu_notifier.py    # 飞书审批卡片推送与回执格式化
└── references/               # 历史评测报告与战报归档
```

---

## 三、 五大核心机制设计

### 1. 配置驱动（1A）
在 `config/vendors.yaml` 中结构化声明指定供应商元数据：
- `vendor_id`：供应商代号（如 `cline`, `qoder-cn`, `nvidia`, `amd`）
- `doc_url`：官方文档与模型规格页
- `events_url`：官方优惠/活动目录（或 `llms.txt`）
- `api_endpoint`：模型枚举接口（如 `/v1/models`）
- `known_specs`：官方已声明的上下文上限、免费额度、RPM 限制（声明则跳过大包盲探）

### 2. 三态智能触发与测试分层（3A + 规约优先）
- **态 1 · 极轻心跳（日常巡检）**：
  - 构造极小请求（1-2 token，`max_tokens=1`），仅打探活与首字延迟；
  - 消耗几乎为 0，单发耗时 <2s，每 2~4 小时跑一次。
- **态 2 · 规约校验与深水探针（新上线 / 文档变动）**：
  - 官方已明确标明参数（如已写明 128K 上下文）：仅作最小抽样核准，不烧大包；
  - 官方未写明限制（当谜语人）：触发五维全量探针（扣基线两发校准、二分测上下文、6 发测 429 阈值、测流式吐字速度），把真实参数逼出来。
- **态 3 · 故障诊断（心跳连续异常）**：
  - 连续 2 次心跳失败时触发，区分网络拥堵（超时）、凭据失效（401/403）还是模型下架（404/模型不存在）。

### 3. 数据底座（4A）
SQLite 数据库：`~/.hermes/data/model-radar.sqlite`
- **表 1 · `models_current`（当前态快照）**：
  - `model_id`, `vendor`, `full_path`, `official_specs`, `measured_specs` (tps, max_ctx, rpm), `status` (alive/degraded/dead), `verdict` (primary/fallback/deprecated), `last_heartbeat`, `updated_at`
- **表 2 · `probe_history`（历史流水表）**：
  - `id`, `model_id`, `probe_type` (heartbeat/benchmark/diagnostic), `latency_ms`, `tps`, `http_code`, `error_raw`, `created_at`
  - 自动保留 30 天，超时自动修剪。

### 4. 10Router 联动与半自动审批卡片（2B）
- 读取 10Router 现行组合（`combos` 表中的 `my-com1`, `yangmao` 等）；
- 计算模型健康度与推荐变动，向飞书输出格式化 diff 表：
  ```markdown
  【10Router 免费模型轮替审批卡片】
  监测到供应商模型池有更优排位，建议调整 combo: [yangmao]
  --------------------------------------------------
  当前排位: ["zcode/glm-5.3-flash", "cline", "qoder", ...]
  推荐排位: ["zcode/glm-5.3-flash", "新主力A", "cline", ...]
  变动原因: 新主力A 实测 85 tok/s，上下文 128k 全绿，评定为【可当主力】
  --------------------------------------------------
  👉 老板若同意调整，请直接回复【同意变更】或【采纳】，小兔立即代为下发网关！
  ```
- 老板审批确认后，由小兔调用更新接口安全热更 10Router 数据库与生效。

### 5. 落地执行步序（5A）
- **第一阶段**：编写配置模板、数据库迁移脚本、测试器与建议生成模块；
- **第二阶段**：选定 1-2 家现有活跃免费供应商（如 `cline`、`qoder-cn`）进行真实 CLI 端到端探测；
- **第三阶段**：验证数据库写入、diff 建议生成以及飞书消息卡片生成；
- **第四阶段**：老板验收通过后，配置 Hermes 定时任务正式挂载常态化巡检。
