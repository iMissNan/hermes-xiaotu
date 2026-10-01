---
name: self-hosted-app-upgrade
description: 自托管应用与版本雷达安全升级总管 (v2.2.0)——配置驱动化架构 (upgrade-apps.json)，支持多别名与多应用拓扑串行联合升级（如「cd 和 10r 升级」）；具备版本一致极速秒回、升级前预检护甲、一键后悔药回滚 (rollback-runner)、双重补丁台账隔离与波次合并两段式闭环交付。
version: 2.2.0
---

# 自托管应用版本雷达与安全升级总管 (App Upgrade Radar & Safe Engine v2.2.0)

本技能为家庭服务器自托管开源应用与 AI 基础设施的标准化升级中枢。统一纳管 Git 源码克隆型、Docker 容器型、GitHub Releases 单二进制型与 NPM 全局包型多源资产。

---

## 一、 核心特性与交互范式 (Features & Workflows)

### 1. 触发方式与别名宽容映射
- **单应用精准/别名触发**：
  - 支持应用 ID、官方名及通俗别名（如 `cd 升级`、`10r 升级`、`积分管家 检查更新`、`clash 升级`、`密码库 升级`）；
- **多应用拓扑串行升级触发**：
  - 支持多任务并列句式：“`creditdaddy, 10router 升级`”、“`cd 和 10r 一起升级`”；
  - 自动通过 `resolve-apps.py` 进行依赖拓扑排序（按 `infra -> gateway -> service -> dashboard` 升序逐个安全推进）；
- **全盘版本雷达触发**：`版本雷达` / `自托管更新巡检` / `检查全部组件更新`。

### 2. 版本一致秒回阻断机制（体验防焦虑与零空转）
在第一阶段巡检中，比对本地基线（Tag 与 Commit SHA）与上游远端：
- 若判定 **本地与上游完全齐平（落后 0 提交且 Tag 一致）**：
- **立即熔断，直接输出 1 秒极速回执**，严禁进入第二阶段，严禁输出虚假施工方案或引发服务无意义重启！

#### 极速回执模板：
```markdown
# 🟢 [应用名] 处于最新版本（无需升级）

- **当前运行版本**：`vX.Y.Z` (Commit `abc1234`)
- **上游远端状态**：`origin/main` 同样为 `abc1234`（落后 0 提交）
- **健康状态**：服务在线，核心端口正常，本地专属补丁完好在位。
- **结论**：本地与官方主线完全齐平，当前无需执行任何升级操作！🐰
```

### 3. 多任务拓扑串行与级联熔断铁律
当遇到多应用联合升级时：
1. **拓扑依赖顺序**：先升底层基础设施（infra/gateway），再升上层服务（service），最后是大盘（dashboard）；
2. **严禁并发抢占 CPU**：奔腾 G3220 双核低算力环境下，**必须严格串行排队执行**；
3. **级联熔断防雪崩**：前置应用若在升级、单测或对拍中出现任何失败，**立即就地回滚前置应用，并强行阻断后续所有应用升级**！

---

## 二、 配置驱动化架构 (~/.hermes/config/upgrade-apps.json)

系统核心资产已从文档硬编码彻底解耦为统一配置文件：`~/.hermes/config/upgrade-apps.json`。
**后续新增任何应用，仅需向该文件追加一个配置块，Skill 与版本雷达全自动识别**。

### 注册表结构规范 (Schema)：
```json
{
  "topology_ranks": { "infra": 1, "gateway": 2, "service": 3, "dashboard": 4 },
  "apps": {
    "<app_id>": {
      "name": "应用显示名称",
      "provider": "git-source | binary-release | docker-image",
      "tier": "infra | gateway | service | dashboard",
      "aliases": ["别名1", "别名2"],
      "workdir": "工程工作区路径",
      "repo": "上游 Git 仓库地址",
      "branch": "追踪分支 (默认 main)",
      "service": "Systemd 服务名称",
      "systemd_level": "system | user",
      "port": 47860,
      "patch_dir": "工程内补丁路径",
      "patch_mirror_dir": "主目录集中归档路径 (~/.local-patches/<app>)",
      "test_cmd": "门禁单测命令 (如 npm test)",
      "preflight": {
        "min_disk_free_mb": 2048,
        "check_port": 47860
      },
      "verify": {
        "status_url": "健康检查 URL",
        "assert_json": { "ok": true },
        "whitelist_host": "合法的内网/反代 Host (正向 200)",
        "forbidden_host": "未授权的 Host (反向 403)"
      }
    }
  }
}
```

---

## 三、 本地专属补丁双重归档与一键后悔药

### 1. 双重镜像持久化铁律
专属补丁与台账必须在两处同时落盘持久化，严禁只凭记忆：
1. **工程自包含镜像**：`<app-path>/local-patches/`（随工程一同冷备）；
2. **主目录集中台账镜像**：`~/.local-patches/<app>/`（永久独立于工程目录，防止工程误删/重建导致补丁蒸发）。

### 2. 升级执行辅助工具链 (`scripts/`)
技能自带经过生产验证的极简可执行套件：
- `resolve-apps.py <query>`：别名解析与依赖拓扑排序；
- `preflight-guard.py <app>`：升级前体检（磁盘 $\ge 2\text{GB}$、在途打卡互斥、端口与补丁检查）；
- `record-history.py`：升级/回滚台账自动追加记入 `~/.hermes/state/upgrade-history.jsonl`；
- `rollback-runner.py <app> [backup_dir]`：**一键后悔药**，原子化还原源码与数据，秒级拉起旧版并验证。

---

## 四、 标准两段式交互流程与交付模板

### 1. 第一阶段：巡检审计与方案呈报（只查不改）
- 提取本地当前运行态；抓取上游最新 HEAD / Release；
- 若无更新 $\to$ 输出极速一致回执并退出；
- 若有更新 $\to$ 运行 `preflight-guard.py`，出具方案、风险画像与回滚预案，**停手等待老板拍板**。

### 2. 第二阶段：批准施工与多任务串行推进
- 老板回复“升级 / 安全更新 / 执行升级”后启动；
- 针对任务列表按拓扑逐个执行：冷备 $\to$ 更新 $\to$ 补丁改回 $\to$ 测试门禁 $\to$ 重启 $\to$ 对拍；
- 记录台账 `record-history.py`，呈报多任务/单任务对拍报告。

#### 交付简报模板：
```markdown
# 🚀 自托管安全升级交付简报 (N/N 完成)

| 应用名称 | 升级前 | 升级后 | 单测门禁 | 本地补丁 | 最终状态 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **[应用A]** | v旧 | v新 | N例全绿 | 依据台账改回 | ✅ PASS (耗时 Ns) |
| **[应用B]** | v旧 | v新 | 门禁通过 | 依据台账改回 | ✅ PASS (耗时 Ns) |

- **关联联动对拍**：[跨服务连通性测试回执]
- **备份与审计锚点**：`~/backups/...` & `~/.hermes/state/upgrade-history.jsonl`
```
