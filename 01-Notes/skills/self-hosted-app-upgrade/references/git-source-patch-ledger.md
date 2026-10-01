# Git 源码型应用专属补丁台账与双重隔离实施手册 (Git-Source Patch Ledger)

## 一、 为什么必须实行「双重镜像台账」
自托管环境中，许多开源项目需长期保留针对本地网络（反向代理 Host 白名单、Tailscale 域名放行、无头验证码求解器、网关别名路由）的专属改动。
- **机制与风险**：若仅将补丁保存在工程内或使用 `git stash`，一旦遇到 `git reset --hard`、工程重克隆或上游构建清理，定制代码将彻底丢失；若仅保存在外部，工程本身丧失自包含性。
- **铁律**：实行「工程内自包含 + 用户主目录集中归档」双重镜像备份：
  1. 工程内：`<app-path>/local-patches/`
  2. 主目录：`~/.local-patches/<app>/`

---

## 二、 补丁文件与台账规范

### 1. 文件组织结构
```text
~/.local-patches/<app>/
├── 0001-fix-daemon-host-whitelist.patch
├── 0002-fix-headless-captcha-solver.patch
└── README.md
```

### 2. 台账 (`README.md`) 必须包含的字段
每个补丁必须在 `README.md` 中记录四要素：
1. **补丁编号与名称**：例如 `PATCH-001-DAEMON-HOSTS`
2. **目标文件与行号/函数**：例如 `src/daemon.js` 中的 `function localHosts()`
3. **注入原因与错误现象**：记录不注入时会触发的明确 HTTP 状态码或报错（如免密模式拦截反代域名报 403）
4. **升级后改回与正反双向验收命令**：
   - 正向放行：真实反代域名/参数访问返回 HTTP 200
   - 反向拦截：恶意/未授权 Host 访问精准返回 HTTP 403

---

## 三、 标准升级与回灌标准循环 (SOP)

### 步骤 0：升级前预检护甲 (Pre-flight Guard)
- **磁盘水位核验**：执行 `df -h / /opt`，确认剩余可用空间 $\ge 2\text{GB}$，防解压与构建中途锁死；
- **在途任务互斥**：检查应用是否有后台任务正在执行（如 CreditDaddy API `/api/status` 中的 `scheduler.ticking === false`）；若正在执行则稍候再重启，避免在途签到或导出数据写裂；
- **即时穿透探真**：对于高频更新项目，使用 `git ls-remote --heads origin <branch>` 探测最新远程 SHA，严禁依赖过期本地缓存。

### 步骤 1：同步与锁定补丁镜像
在动手拉取上游前，确保双重镜像完全一致：
```bash
mkdir -p ~/.local-patches/<app> <app-path>/local-patches
# 将当前生效定制导出为 patch 并归档
git -C <app-path> format-patch -1 <COMMIT_SHA> -o <app-path>/local-patches/
cp -a <app-path>/local-patches/* ~/.local-patches/<app>/
```

### 步骤 2：上游代码拉取与对齐
```bash
git -C <app-path> fetch origin <branch>
git -C <app-path> reset --hard origin/<branch>
```

### 步骤 3：依据台账逐项改回
```bash
# 预检补丁冲突
git -C <app-path> apply --check ~/.local-patches/<app>/<patch-file>.patch
# 真实应用
git -C <app-path> apply ~/.local-patches/<app>/<patch-file>.patch
# 重新提交本地维护 commit，严禁遗留未提交的修改，保证工作区 clean
git -C <app-path> commit -am "fix(<module>): 依据 local-patches 改回专属配置"
```

### 步骤 4：自动化门禁与平滑重启
1. **静态语法检查**：
   - Node: `node --check <entrypoint>`
   - Python: `python3 -m py_compile <files>`
2. **全套单测跑测**：运行自带测试套件（如 `npm test`），必须 100% pass。
3. **服务重启**：`systemctl restart <service>`。

### 步骤 5：四重视角端到端正反双向对拍验收
1. **进程活跃度**：`systemctl is-active <service>` 返回 `active`。
2. **资产完整性**：核心 API 查询确认账号数、凭据数与升级前台账严格一致，无静默丢失。
3. **正反双向对拍**：
   - 携带反代 Host（`Host: <domain>`）请求，确认返回 200；
   - 携带恶意 Host（`Host: evil.com`）请求，确认精准拦截返回 403。
4. **跨服务联动**：调用关联依赖服务的探针端点，确认双向调用连通。

---

## 四、 多任务联合升级与拓扑级联熔断 (Multi-Task Topology & Cascade Guard)

当用户同时指定升级多个组件（如「creditdaddy 和 10router 升级」）时：
1. **拓扑排序**：通过 `scripts/resolve-apps.py` 将应用按底层依赖等级排序（`infra:1 -> gateway:2 -> service:3 -> dashboard:4`）。
2. **严格串行排队**：奔腾/低算力双核环境下，严禁并发执行构建或全量测试；必须等待前置组件全部通过并对拍成功后，再推进下一个。
3. **级联熔断与就地回滚**：
   - 若前置组件（如 10Router）升级失败或测试不通过，立即触发 `rollback-runner.py` 就地回滚该组件；
   - 坚决阻断后续所有依赖组件（如 CreditDaddy）的升级，交出停手回执，防止产生级联故障雪崩。

---

## 五、 一键后悔药回滚规程 (Atomic Rollback SOP)

任何阶段验收失败或用户要求撤回：
1. 执行 `python3 scripts/rollback-runner.py <app>`；
2. 自动定位 `~/backups/<app>/` 下最新一次 `pre-*` 备份锚点；
3. 原子化停止服务 -> 还原源码目录与数据目录 -> 恢复旧版守护进程 -> 端到端验证旧版 API 恢复正常；
4. 审计台账记录：调用 `python3 scripts/record-history.py <app> rollback <from> <to> SUCCESS` 追加日志。

---

## 六、 版本一致极速熔断规程 (Zero-Gap Fast Exit)

在巡检与方案生成阶段，若比对发现本地版本（Commit SHA 与 Release Tag）与远端完全一致：
- **触发条件**：`git rev-list --count HEAD..origin/<branch>` 为 0 且无新 Tag；
- **执行动作**：1 秒极速输出「🟢 处于最新版本，无需升级」确定性回执，并立即终止后续执行，严禁进入施工方案，防止服务器无意义重启。
