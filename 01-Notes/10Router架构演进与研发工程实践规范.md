# 10Router 架构演进与研发工程实践规范

> 关联技能：`ai-infra/ai-gateway-ops`、`10router`
> 上游源头：[techysy/10router](https://github.com/techysy/10router)

---

## 1. 架构核心三定律

1. **协议以 OpenAI 为唯一轴心（Hub & Spoke）**：
   - 拒绝 $N \times M$ 网状互转；所有非标上游或非标下游，统一以 OpenAI Chat/Completions 格式为中间基准转译，仅高损脆弱链路开放 direct 旁路。
2. **切面插件严格遵循故障开放（Fail-Open）**：
   - RTK 压缩、Token 节省与请求拦截必须包裹全局 fail-open，任何内部异常必须原样放行原始 Payload，宁可牺牲优化，绝不允许中断上层业务。
3. **单核代码的多端宿主封装（Multi-Target Packaging）**：
   - 核心服务依托 Next.js standalone（纯 Node.js 服务）；桌面端通过 `ELECTRON_RUN_AS_NODE=1` 直接将其作为 Sidecar，零打包额外 Node 运行时，一套代码服务 Docker / Desktop / CLI / NAS / Plugin 五种形态。

---

## 2. 研发与质量防线（QA & Release）

1. **敏捷小步快跑（Trunk-based Development）**：
   - 无长期巨型分支，按 Conventional Commits 规范微步合入 main，高频触发 CI 镜像构建。
2. **Issue 驱动的契约锁定测试（Contract Pinning）**：
   - 凡报 Bug 必在 `tests/` 补入 issue 编号命名测试用例，真实断言 HTTP 请求与响应字节流，锁定边界，严防版本回退与退化。
3. **复杂数据的运维手术刀化（Surgical Tooling）**：
   - SQLite 统计与日桶漂移不通过暴力重构解决，通过独立维护只读体检（`verify-usage-db`）与停服备份清理（`clean-usage-db`）脚本化解运维风险。

---

## 3. Agent 优先（Agent-Native）交付范式

1. **细粒度能力技能分离**：
   - 将多模态能力解耦为独立的一级技能卡（chat、image、video、tts、stt、embeddings、web-search、web-fetch），单卡职责单一，防止大模型上下文污染。
2. **运行态自服务扩容（Self-Serve Routing）**：
   - 网关向 Agent 开放特定免登/自服务鉴权 API（`10router-add-provider`），支持 Agent 运行态自主挂载新上游，无需改动源码、无需重启网关。
