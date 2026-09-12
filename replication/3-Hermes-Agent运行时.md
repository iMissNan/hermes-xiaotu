# 3-Hermes-Agent运行时

> 一句话：全系统的 AI 大脑本体——Hermes Agent（CLI + 网页版 + 消息网关），所有模型流量经第 2 章 10Router 出去。

## 1. 是什么

Hermes Agent 是开源的 AI 助手运行时（CLI 交互、Web UI、消息平台网关三形态）。家庭系统里它同时是：日常 AI 助手、自动化引擎（cron 任务/技能系统）、以及上层工作流（第 12 章 AO）的执行底座。

## 2. 上游原址

- 项目仓库：https://github.com/NousResearch/Hermes-Agent （看仓库 README 获取安装文档）
- 官方文档：https://hermes-agent.nousresearch.com/docs
- 安装方式：官方推荐 venv + pip；本机为 `~/.hermes/hermes-agent/`（venv）+ Node 23（webui 运行时）

## 3. 部署

### 3.1 Node 运行时（webui 依赖）

```bash
# Node 23（本机实测版本；装在用户目录免 sudo）
mkdir -p ~/.local/opt && cd ~/.local/opt
# 从 nodejs.org 下载 linux-x64 的 node23 发行包解压至 ~/.local/opt/node23
export PATH=~/.local/opt/node23/bin:$PATH
node -v   # v23.x
```

### 3.2 Hermes 本体

```bash
python3 -m venv ~/.hermes/hermes-agent/venv
~/.hermes/hermes-agent/venv/bin/pip install hermes-agent   # 以官方文档安装名为准
~/.hermes/hermes-agent/venv/bin/hermes setup               # 交互式初始化（选自定义 provider）
```

**模型接入（关键步）**：初始化时选择 custom provider 指向本机 10Router——

- API Base：`http://<内网IP>:20128/v1`
- API Key：10Router 面板创建的令牌
- 模型名：10Router 面板中配置的模型/组合名

### 3.3 网页版（系统级服务）

systemd 单元 `/etc/systemd/system/hermes-webui.service`（需 root 安装）：

```ini
[Unit]
Description=Hermes Web UI
After=network.target

[Service]
User=<你的用户>
ExecStart=/home/<你>/.local/opt/node23/bin/node /home/<你>/.hermes/webui/server.js
Restart=on-failure
Environment=PORT=8648

[Install]
WantedBy=multi-user.target
```

> 注：webui 入口文件名以你安装版本的官方文档为准（本机取证 ExecStart 为 node 启动 `~/.hermes` 下 webui 程序，:8648）。

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now hermes-webui
```

### 3.4 消息网关（可选，接飞书/Telegram 等）

用户级单元 `~/.config/systemd/user/hermes-gateway.service`：

```ini
[Unit]
Description=Hermes Agent Gateway - Messaging Platform Integration
After=network.target

[Service]
ExecStart=%h/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run
WorkingDirectory=%h/.hermes
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now hermes-gateway
```

平台的 app id/secret 在 `hermes` 对应渠道配置中填写（见官方文档 messaging 章节）。

## 4. 配置

- 主配置：`~/.hermes/config.yaml`（provider/模型/思考强度/工具开关；`hermes config set` 命令式修改）；
- 技能库：`~/.hermes/skills/`（本仓 `01-Notes`/`02-Projects` 记录的多个技能实践可迁入）；
- **双辅助模型建议**：vision 识图模型与主模型分开配置（10Router 里路由两个组合名）。

## 5. 数据重建

- 会话历史：`~/.hermes/` 下会话库，新装即空，随使用生长；
- 技能：从本仓 skills 相关笔记按需重建；
- 不迁移任何对话数据（可换皮原则）。

## 6. 服务联动

- 依赖：2（10Router 模型出口）、0（Python/Node）；
- 被依赖：12（AO 工作流以 hermes-cli 为执行引擎）、4（aiduMEM 挂钩 Hermes 记忆管道）；
- 网关让手机/IM 直达这套系统（飞书卡片渲染需配套插件，见上游仓库）。

## 7. 验证

```bash
hermes --version
echo hi | hermes run "回复ok两个字母即可"    # 走 10Router 的真实推理一轮
curl -sI http://<内网IP>:8648 | head -1      # webui 门通
systemctl --user is-active hermes-gateway    # 网关在位（如部署）
```

## 8. 升级与回滚

```bash
~/.hermes/hermes-agent/venv/bin/pip install -U hermes-agent
systemctl --user restart hermes-gateway && sudo systemctl restart hermes-webui
```

- 升级前 `cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak`；行为异常回滚 pip 版本号即可。
- 升级后过一遍第 7 节验证（尤其模型链路）。
