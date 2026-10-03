---
name: free-model-radar
description: 10Router 免费模型常态化雷达巡检、按规校验、深测排位与半自动换血审批。
version: "2.0.0"
---

# free-model-radar（免费模型雷达）

本技能实现 10Router 免费模型的常态化自动巡检、按规探查、前哨对拍、审批换血，达成「常用、能用、好用、一直用」。

## 核心原则与模型准入规范（穿透铁律）

### 0. 【Rule 0】前哨独立发现与强制网关对拍铁律（最高铁律，不可妥协）
- **致命根因防范**：严禁只对接 10Router 网关配置或官网静态营销页（例如 docs.cline.bot 等静态文档），静态网页永远慢人一步且极易被 404/重定向误导。
- **动态货架机制破案**：Cline 等主流 AI 编码工具的免费模型并非公开展示在静态网页上，而是由客户端服务端 API 动态下发的（如 `https://api.cline.bot/api/v1/ai/cline/recommended-models`），属于**“IDE/CLI 客户端动态货架模型”**。
- **强制一手前哨发现**：雷达前哨必须配置本地代理（`http://127.0.0.1:7892`）直连官方客户端推荐接口，一手探测当期真正 free 货架与 OpenRouter `:free` 开放免费池。
- **强制三差集硬核对拍**：一手发现结果必须与 10Router 现网（`kv` 表别名映射 + `providerConnections.modelLock`）进行硬核对拍，严格产出三大差集：
  1. `dual_matched`（双向对齐）：官方货架当期在售，且 10Router 网关已挂载生效；
  2. `newly_discovered`（外部新出、网关漏配）：官方动态一手新出，但 10Router 网关尚未配置，触发补录告警；
  3. `ghost_mounted`（外部已下架、网关幽灵挂载）：官方动态货架已下线除名，但 10Router 网关仍残留挂载，触发剔除建议。
- **执行硬性约束**：该步骤不可省略、简化和跳过！

### 1. 永久免费 vs 促销额度池（HTTP 402 vs 404 严格区分）
- **真·Free 货架模型**：官方动态接口 `free` 数组明确列出，无账号扣费壁垒（如 `cline-free/deepseek-v4.1-flash`, `stealth/space-bunny-alpha`, `cline-free/mimo-v2.6-flash`, `cline-free/muse-spark-1.3-contributor`, `qwen/qwen3.8-27b:free`, `poolside/laguna-s-2.1:free`）；
- **促销体验额度池（Promotional Credits）**：如 Kimi K3 (`cl/moonshotai/kimi-k3`) 与 Gemini 3.8 Flash (`cl/google/gemini-3.8-flash`) 属于 ClinePass / 新用户体验促销池，需要账号自带赠送额度。老账号余额不足时上报 **HTTP 402（`insufficient_credits`）**，**严禁将其判定为 404（模型下架）**！台账与探针必须精准标注 `🟡 额度尽 (402)`。

### 2. 原子模型三源穿透校验原则（严禁将 Combo 组名当作模型）
- **禁止项**：严禁直接抓取或使用 10Router 网关的 `combos` 组名（如 `AMD`、`qoder`、`cline`、`NVIDIA`）当作单体模型进行登记与测试；
- **强制三源对拍**：
  1. **源 1 · 官网/动态货架接口**：抓取官方公布的真实模型代号（如 AMD 的 `Qwen3.8-Flash-Next`，绝无叫 AMD 的模型）；
  2. **源 2 · 网关实体连接（`providerConnections.modelLock`）**：必须是真实挂在某个供应商连接下的原子模型；
  3. **源 3 · KV 路由别名**：检查 `kv` 表中的 `providerAlias|modelId|llm` 映射。
- **判读标准**：只有在三源中均能证明是**原子模型**（Atomic Model）的，才允许作为模型入库。凡是聚合列表、快捷组，统统剥离！

### 3. 供应商服区（Region）物理隔离准则
- 凡存在“国服（CN）”与“国际服（Global/Intl）”之分的供应商，**必须在供应商 ID、文档入口与模型前缀上强制物理分流**：
  - **Qoder 国服**：ID 锁定为 `qoder-cn`，官方入口 `qoder.cn`，网关端点前缀 `qdc/`（如 `qdc/qfmodel`, `qdc/qmodel_38max`）；
  - **Qoder 国际服**：ID 锁定为 `qoder`，官方入口 `qoder.sh` / `qoder.com`，网关端点前缀 `qd/`（如 `qd/qfmodel`, `qd/qmodel_38max`）。
- **禁止项**：严禁使用模糊的“qoder”统称，报表和台账必须明确标注 `【Qoder 国服】` 或 `【Qoder 国际服】`。同样适用于 CodeBuddy 等多服区供应商。

### 4. 规约优先（Specification First）与测试分层
- 若 `config/vendors.yaml` 中某个模型已注明官方参数（如 `context_length: 128000`），L2 测试仅做最小抽样核准（1发验证），严禁盲发 32K/131K 探测包烧光配额；
- **L1 极轻心跳（日常巡检/现场查探）**：单发 25 token，涵盖文本、思考链 (reasoning)、流式 chunk 信号穿透，极速验证存活与首字延迟；
- **L2 规约核验与深测**：新上线/心跳异常/周期性深测时触发，覆盖存活、延迟、吞吐 (TPS)、上下文容纳、限流退避。

### 5. 独立数据底座
- 数据库：`~/.hermes/data/model-radar.sqlite`
- `models_current`：当前态快照（各模型最新状态、官方与实测参数、推荐判定）。
- `probe_history`：30 天流水明细表，自动滑动清理。

## 四环联动探查流水线（do_investigate）

在执行 `fm查 <供应商>` 时，完整触发四环联动流水线：
1. 📡 **环 1 · 官方客户端动态货架一手发现**：直连官方客户端推荐接口，提取当期 real free 货架与开放免费池；
2. 🔍 **环 2 · 10Router 现网硬核差集对拍**：计算 Dual Matched（双向匹配）、Newly Discovered（新发现漏配）、Ghost Mounted（网关幽灵挂载）；
3. ⚡ **环 3 · 现场真流量实测与入库快照**：现场对原子模型发包打流，精准识别 `🟢 稳活 (200)`、`🟡 额度尽 (402)`、`🔴 下架 (404)`、`🟡 限流 (429)` 与超时；
4. 💡 **环 4 · 运维决策与换血指引**：针对幽灵挂载给出剔除建议，针对新发现给出补录建议，并提供一键换血指令。

## 目录结构

```
free-model-radar/
├── SKILL.md                  # 技能正本与操作指引（含 Rule 0 与四环规范）
├── config/
│   └── vendors.yaml          # 供应商花名册、已知规约与端点配置
├── scripts/
│   ├── run.py                # 主控制入口（CLI 调度与四环流水线落地）
│   ├── crawler.py            # 前哨独立发现引擎与 10Router 差集对拍器
│   ├── probe_engine.py       # L1/L2 两级探针测试引擎（流式+思考链）
│   ├── router_advisor.py     # 10Router combos 对齐与 diff 建议
│   ├── cli_handler.py        # 自然语言与短指令路由解析器
│   └── feishu_notifier.py    # 飞书审批卡片生成器
└── references/               # 历史评测报告与战报归档
```

## CLI 快速使用

### 1. 底层 CLI 指令 (run.py)

```bash
# 1. 探查指定供应商（触发前哨四环联动流水线）
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode query --vendor cline

# 2. 运行全量 L1 巡检
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode heartbeat [--vendor cline]

# 3. 对特定模型执行 L2 深测（规约优先）
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode benchmark --model cl/stealth/space-bunny-alpha

# 4. 对齐 10Router 生成审批建议与飞书卡片
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode advise --combo yangmao

# 5. 查询今日有效供应商与存活模型大盘
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode active

# 6. 查询今日高性价比免费主力 Top 榜单
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode top

# 7. 安全采纳/写入推荐排位（带备份快照）
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/run.py --mode apply --combo yangmao [--dry-run]
```

### 2. 自然语言 / fm 前缀指令体系 (cli_handler.py)

统一前缀采用 `fm`（Free Model 首字母缩写），避免与其他技能冲突。彻底告别 ASCII 字符块，全链路输出原生 GFM Markdown 表格：

| 前缀指令 | 对应功能与说明 | 示例 |
|---|---|---|
| `fm 指令` / `fm 帮助` / `fm help` / `fm menu` / `fm 菜单` | **全量功能速查菜单**：输出所有指令分类、示例与说明表格，防止遗忘 | `fm 指令`、`fm 帮助`、`fm help` |
| `fm 全部` / `fm 全部供应商` / `fm 当前入库` / `fm 现存` / `fm 活跃` / `fm active` | **方案二供应商分块大盘**：按供应商小标题分块输出原生表格，展示存活模型、延迟、吞吐、上下文与定位，自动过滤失效供应商 | `fm 全部`、`fm active`、`fm 当前入库` |
| `fm 榜单` / `fm top` / `fm 排行榜` | **优质主力推荐榜**：按存活/主力/吞吐/延迟智能打分，输出原生 Markdown Top 推荐榜单 | `fm 榜单`、`fm top`、`fm top 3` |
| `fm查` / `fm 查` / `fm查询` / `fm list` / `fm status` | **前哨四环联动探查**：执行前哨一手发现 ➔ 现网差集对拍 ➔ 现场流量探活 ➔ 换血决策指引 | `fm查`、`fm 查 cline`、`fm查 qoder`、`fm查询 cline` |
| `fm加` / `fm添加` / `fm add` | **花名册登记**：登记新供应商或模型至 `vendors.yaml` | `fm加 --vendor siliconflow --doc-url https://siliconflow.cn --models m1,m2` |
| `fm测` / `fm test` / `fm benchmark` | **轻重心跳与深测**：即时触发 L1 心跳（规约优先）或 L2 规约深测 | `fm测`（全量巡检）、`fm测 cline`、`fm测 cl/stealth/space-bunny-alpha`（深测） |
| `fm换` / `fm采纳` / `fm apply` | **一键换血采纳**：采纳推荐排位，自动生成快照备份并更新 10Router 网关 | `fm换`、`fm换 yangmao`、`fm采纳 yangmao` |
| `fm停` / `fm删` / `fm remove` / `fm disable` | **移除供应商**：停用或从花名册中剔除失效供应商 | `fm停 cline`、`fm删 nvidia` |

可以直接在终端调用：
```bash
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/cli_handler.py "fm 指令"
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/cli_handler.py "fm 全部"
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/cli_handler.py "fm 榜单"
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/cli_handler.py "fm 查 cline"
python3 /home/linxuan/.hermes/skills/ai-infra/free-model-radar/scripts/cli_handler.py "fm换 yangmao"
```
