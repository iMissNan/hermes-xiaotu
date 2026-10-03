# free-model-radar v3.0 独立双轨前哨雷达架构设计书

> 日期：2026-10-03  
> 状态：老板明确纠偏后迭代定案（告别 10Router 旧账依赖，确立独立前哨真理底座）  
> 核心目标：构建 100% 独立于网关的外部第一手探测源，快人一步感知新上架与限免模型，以真实差集反向赋能 10Router 换血与自愈。

---

## 一、 系统定位与根本纠偏

### 1. 历史教训与根本纠偏
- **历史盲区**：此前雷达在外部未直接解析到表格时，错误地回退读取 10Router 网关本地的注册表或配置。这导致角色严重错位——**“侦察兵不去前线侦察，反而跑回自家的旧军械库翻旧账，永远慢人一步”**。
- **根本定位**：`free-model-radar` 是**独立走在行业最前沿的前哨雷达**！必须直接把探针插到各家厂商官方的最前沿（动态 API、NPM 发版、官方文档/活动页、官方计费端点），**先于 10Router 发现新模型，再与 10Router 对拍产生差集，反向驱动网关升级换血**！

---

## 二、 四大独立前哨探测源（以点扩面全矩阵）

针对全网主流 AI 工具与供应商的不同分发模式，雷达建立四大标准化一手前哨策略（`strategies/`）：

```
                                  【UniversalRadar 调度引擎】
                                                │
    ┌─────────────────────────┬─────────────────┴─────────────────┬─────────────────────────┐
    ▼                         ▼                                   ▼                         ▼
【策略 1 · ClientDynamicShelf】 【策略 2 · PackageReleaseIntrospect】 【策略 3 · DocTableAndEvents】   【策略 4 · UpstreamQuotaProbe】
(客户端动态 API 货架)        (NPM / GitHub 发版自省)             (官方文档与促销活动页)         (直连厂商计费端点)
代表: Cline / OpenCode        代表: WorkBuddy / Qoder CLI        代表: Qoder / 智谱             代表: 腾讯云 / 阿里百炼
```

### 1. 策略 1 · 客户端动态货架（`dynamic_shelf`）
- **探测逻辑**：直连厂商客户端专属服务端推荐接口（如 Cline 的 `recommended-models`、OpenRouter 的开放模型接口）；
- **输出**：提取当期真正 `free` 数组与 `promotional` 体验额度池；
- **时效性**：秒级感知，官方服务端配置一改即刻捕获。

### 2. 策略 2 · 官方发布包自省（`package_introspect` —— 攻克 WorkBuddy 等客户端内嵌型的利器！）
- **探测逻辑**：
  - 针对 WorkBuddy（CodeBuddy）、Qoder CLI 等将模型内嵌在客户端工具链中的厂商；
  - 雷达直接请求官方 NPM Registry（如 `https://registry.npmjs.org/@tencent-ai/codebuddy-code/latest`）；
  - 检查官方最新发版版本号，并在内存中轻量解构其最新发布包中的 `models.json` 或常量表；
- **时效性**：**比 10Router 快数天！** 厂商官方发包的第一秒，雷达便率先捕获新模型定义。

### 3. 策略 3 · 官方文档与实时活动页（`doc_table`）
- **探测逻辑**：
  - 请求官方文档模型矩阵（如 `docs.qoder.cn/cli/model`）与活动优惠目录（如 `events/flashoffer`）；
  - 解析 HTML / Markdown 表格，正则捕获原子模型代号、上下文规格（200K, 400K, 1M）与 0 Credits / 错峰打折说明；
- **时效性**：直接对齐官方公开承诺与政策变动。

### 4. 策略 4 · 官方协议计费端点直连（`upstream_billing`）
- **探测逻辑**：
  - 针对国内云厂商（腾讯云 CodeBuddy、魔搭），直接使用本地活 Token 敲其官方查询端点（如 `copilot.tencent.com/v2/billing/meter/get-user-resource`）；
  - 提取官方下发的真实账户算力包、当前剩余额度与免额规则；
- **时效性**：真实穿透官方风控与免额时间窗（如夜间免费）。

---

## 三、 四环前哨联动流水线（全生命周期闭环）

不论触发哪个供应商（`fm 查 <供应商>`），均严格按四环流水线推进：

```
1. 📡 环 1 · 官方一手动态前哨探查 (Sniff)
   └─ 调用策略 1/2/3/4 独立抓取官方当期所有模型、上下文、0倍率政策（标注探测源）
         │
         ▼
2. 🔍 环 2 · 10Router 现网硬核差集对拍 (Cross-Check)
   ├─ 读取 10Router 现网真实激活账号态 (Active / Inactive 预警)
   ├─ 与 10Router 现网已装配模型做数学差集：
   │    * Dual Matched (双向对齐)
   │    * Newly Discovered (外部新出、网关漏配 ➔ 重点标出！)
   │    * Ghost Mounted (外部已下线、网关残留幽灵 ➔ 重点标出！)
         │
         ▼
3. ⚡ 环 3 · 现场真流量实测与入库快照 (Probe & Live Traffic)
   ├─ 对该供应商主力模型打真实业务流量（验证 200 稳活、402 额度尽、404 下架、429 限流）
   ├─ 测出真实 首字延迟 (s)、流式吞吐 (tok/s)
   └─ 写入独立数据库 ~/.hermes/data/model-radar.sqlite models_current 表
         │
         ▼
4. 💡 环 4 · 运维决策与换血指引 (Advise & Action)
   ├─ 对 Newly Discovered 输出一键补录建议 (前缀、代号)
   ├─ 对 Ghost Mounted 输出一键剔除建议
   └─ 推荐主力排位，支持 `fm换 yangmao` 一键同步网关
```

---

## 四、 配置规格设计（`config/vendors.yaml`）

统一结构化声明外部一手前哨源，彻底废除代码分支：

```yaml
vendors:
  workbuddy-cn:
    vendor_id: "workbuddy-cn"
    name: "WorkBuddy 国服 (CN)"
    doc_url: "https://www.codebuddy.cn/docs/cli/models"
    discovery:
      type: "package_introspect"
      package_name: "@tencent-ai/codebuddy-code"
      registry_url: "https://registry.npmjs.org/@tencent-ai/codebuddy-code/latest"
      fallback_doc_url: "https://www.codebuddy.cn/docs/cli/models"
    gateway_binding:
      alias_prefixes: ["cbcn"]
      provider_names: ["workbuddy-cn", "codebuddy-cn"]

  workbuddy:
    vendor_id: "workbuddy"
    name: "WorkBuddy 国际服 (Intl)"
    doc_url: "https://codebuddy.ai"
    discovery:
      type: "package_introspect"
      package_name: "@workbuddy/cli-vnext"
      registry_url: "https://registry.npmjs.org/@workbuddy/cli-vnext/latest"
      fallback_doc_url: "https://codebuddy.ai"
    gateway_binding:
      alias_prefixes: ["cbai"]
      provider_names: ["workbuddy", "codebuddy-intl"]

  qoder-cn:
    vendor_id: "qoder-cn"
    name: "Qoder 国服 (CN)"
    doc_url: "https://docs.qoder.cn"
    discovery:
      type: "doc_table"
      url: "https://docs.qoder.cn/cli/model"
      events_url: "https://docs.qoder.cn/events/flashoffer"
    gateway_binding:
      alias_prefixes: ["qdc"]
      provider_names: ["qoder-cn"]

  qoder:
    vendor_id: "qoder"
    name: "Qoder 国际服 (Global)"
    doc_url: "https://docs.qoder.com/zh"
    discovery:
      type: "doc_table"
      url: "https://docs.qoder.com/zh/cli/model"
      events_url: "https://docs.qoder.com/zh/events/flashoffer"
    gateway_binding:
      alias_prefixes: ["qd"]
      provider_names: ["qoder"]

  cline:
    vendor_id: "cline"
    name: "Cline Free Tier"
    doc_url: "https://docs.cline.bot"
    discovery:
      type: "dynamic_shelf"
      url: "https://api.cline.bot/api/v1/ai/cline/recommended-models"
      openrouter_free: true
    gateway_binding:
      alias_prefixes: ["cl", "cline"]
      provider_names: ["cline"]
```

---

## 五、 实施计划与验收门禁

1. **第一阶段：前哨策略扩展**
   - 在 `scripts/crawler.py` 中落地 `sniff_package_introspect()`，请求官方 NPM registry 解析出最新版本和模型定义；
   - 更新 `vendors.yaml` 为 WorkBuddy 配置 `package_introspect`；
2. **第二阶段：端到端真机对拍**
   - 验证 `fm workbuddy国服和国际服`：环 1 必须明确标出由官方 NPM 发版源一手抓取的最新模型与版本号；
   - 验证与 10Router 网关计算出真实的差集（双向匹配、新发现漏配）；
3. **第三阶段：红队复审与归档**
   - 独立红队执行端到端验证，出具报告；
   - Git 提交并推送双平台同步。
