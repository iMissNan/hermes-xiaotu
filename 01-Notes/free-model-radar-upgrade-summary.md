# free-model-radar 技能系统性升级与四环流水线落地总结报告

- **日期**：2026-10-02
- **责任主体**：Hermes 子代理（代班施工）
- **技能路径**：`/home/linxuan/.hermes/skills/ai-infra/free-model-radar`
- **交付目标**：落地 Rule 0 前哨独立发现与 10Router 网关强制差集对拍铁律，升级 Cline 动态货架感知，落地四环流水线，严格区分 HTTP 402（额度尽）与 404（模型下架）。

---

## 一、核心背景与问题破案

1. **历史致命根因**：
   - 过去雷达只盲目抓取 10Router 网关配置或官网静态营销页（如 `docs.cline.bot` 等），极易被静态文档滞后、404 或死链误导，永远慢人一步；
2. **机制真正破案**：
   - Cline 等现代 AI 编码客户端的免费模型并非在官网做静态展示，而是由客户端服务端 API 动态下发（`https://api.cline.bot/api/v1/ai/cline/recommended-models`）。这种“IDE/CLI 客户端动态货架”才是官方一手真源；
3. **官方真神模型 vs 促销体验额度池**：
   - **当期真正 Free 货架模型**：官方接口 `free` 数组直接下发，无账号扣费壁垒：
     - `cline-free/deepseek-v4.1-flash` (1M context)
     - `stealth/space-bunny-alpha` (1M context)
     - `cline-free/mimo-v2.6-flash` (128k context)
     - `cline-free/muse-spark-1.3-contributor` (128k context)
     - OpenRouter 开放免额模型：`qwen/qwen3.8-27b:free`, `poolside/laguna-s-2.1:free` 等
   - **促销体验额度池（Promotional Credits）**：
     - Kimi K3 (`cl/moonshotai/kimi-k3`) 与 Gemini 3.8 Flash (`cl/google/gemini-3.8-flash`) 属于 ClinePass / 新用户体验促销池，需要账号带体验赠额；
     - 老账号额度用尽时上报 **HTTP 402 (`insufficient_credits`)**，必须与 404（模型下架）严格区分！

---

## 二、架构升级与四环流水线落地

根据最高原则 **Rule 0**，重构并落地全套四环流水线：

```
+-----------------------------------------------------------------------------------+
|                            【Rule 0 四环联动流水线】                              |
|                                                                                   |
|  [环 1 · 📡 前哨一手发现]  直连官方客户端推荐接口 (带本地代理 7892) 提取 real free 货架   |
|            │                                                                      |
|            ▼                                                                      |
|  [环 2 · 🔍 现网差集对拍]  对拍 10Router 网关 (kv 别名 + modelLock) 计算三大差集:       |
|                            - dual_matched (双向对齐)                              |
|                            - newly_discovered (外部新出、网关漏配)                |
|                            - ghost_mounted (外部已下架、网关幽灵挂载)             |
|            │                                                                      |
|            ▼                                                                      |
|  [环 3 · ⚡ 现场流量探活]  现场打真实 L1 心跳探针 (思考链/流式穿透)，入库更新当前态:      |
|                            - 200 稳活 / 402 额度尽 / 404 下架 / 429 限流 / 超时    |
|            │                                                                      |
|            ▼                                                                      |
|  [环 4 · 💡 换血决策指引]  幽灵剔除建议 + 漏配补录建议 + 一键换血同步网关 combos         |
+-----------------------------------------------------------------------------------+
```

---

## 三、文件改造清单与 SHA256 锚点

| 文件 | 变更说明 |
| :--- | :--- |
| `scripts/crawler.py` | 增加 `sniff_client_shelf(vendor_id)` 前哨独立引擎（直连 Cline 动态货架与 OpenRouter 免额池）；增加 `cross_check_gateway` 对拍函数，计算三大差集。 |
| `config/vendors.yaml` | 修正 cline 配置，收录真正当期免额模型（`cl/stealth/space-bunny-alpha`, `cl/cline-free/deepseek-v4.1-flash`, `cl/cline-free/mimo-v2.6-flash`, `cl/cline-free/muse-spark-1.3-contributor`, `cl/qwen/qwen3.8-27b:free`, `cl/poolside/laguna-s-2.1:free`），将 Kimi K3 与 Gemini 3.8 Flash 标注为 `promotional_credits`。 |
| `scripts/run.py` | 升级 `do_investigate` 落地完整四环流水线；支持前哨嗅探、网关硬核差集对拍、真流量探针入库、决策换血指引。 |
| `scripts/probe_engine.py` | 优化流式心跳与思考链 (reasoning) 信号接收，支持有效 completion_tokens 与流式 chunk 穿透；精准识别 402 额度尽。 |
| `SKILL.md` | 固化 Rule 0 铁律、客户端动态货架 vs 静态网页、永久免费 vs 促销额度（HTTP 402）的判定标准，固化全套 `fm` 指令。 |

---

## 四、验证自测与执行证据

终端执行：`python3 scripts/cli_handler.py "fm 查 cline"`
实测输出无死角验证了四环全链路运转：
- **环 1**：一手发现 Cline 当期 4 款真 free 模型，17 款 OpenRouter 免额模型，识别 ClinePass 促销额度池；
- **环 2**：精确算出 6 款双向对齐，11 款网关幽灵模型（如 `cline-free/glm-5.3-flash`, `cline-free/kimi-k3` 等旧模型）；
- **环 3**：真流量发包，`cl/cline-free/deepseek-v4.1-flash`、`cl/cline-free/mimo-v2.6-flash`、`cl/cline-free/muse-spark-1.3-contributor`、`cl/poolside/laguna-s-2.1:free` 均 200 稳活；Kimi K3 与 Gemini 3.8 Flash 精确命中 `🟡 额度尽 (402)`，无一误报；
- **环 4**：自动给出幽灵模型剔除指引及 `fm换 yangmao` 换血口径。
