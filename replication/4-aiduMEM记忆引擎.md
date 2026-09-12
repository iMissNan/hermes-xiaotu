# 4-aiduMEM记忆引擎

> 一句话：给 AI 装上长期记忆——全离线部署的记忆引擎（v20.4），为 Hermes 提供跨会话记忆、事实库与人设基座。

## 1. 是什么

aiduMEI（Memory & Wisdom Engine）是自托管长期记忆系统：对话自动提炼入库、语义检索召回、结构化事实库、人格记忆基座。本机为**全离线方案**：LLM 推理走第 2 章 10Router，向量嵌入走本地 embedding-server（127.0.0.1:8769），不依赖任何云记忆服务。

## 2. 上游原址

- 项目：aiduMEI（以部署目录内 README 与版本号为准，本机 v20.4）
- 部署目录：`~/.hermes/aidumem-v204/`（venv + api_server.py）
- 依赖组件：fastembed（e5-large，1024 维）本地 embedding server（自研薄封装，部署见第 3.2 节）

## 3. 部署

### 3.1 embedding-server（本地向量化）

```bash
sudo mkdir -p /opt/embedding-server && sudo chown $USER /opt/embedding-server
cd /opt/embedding-server
python3 -m venv venv
venv/bin/pip install fastembed uvicorn fastapi
# server.py：OpenAI 兼容 /v1/embeddings 薄封装（模型 e5-large，1024 维）
# 模型权重缓存 HF_HOME=/opt/embedding-server/hf-cache，国内走 HF_ENDPOINT=https://hf-mirror.com
```

用户级单元 `~/.config/systemd/user/embedding-server.service`：

```ini
[Unit]
Description=Local OpenAI-compatible embedding server (fastembed e5-large 1024d)
After=network.target

[Service]
WorkingDirectory=/opt/embedding-server
Environment=HF_HOME=/opt/embedding-server/hf-cache
Environment=HF_ENDPOINT=https://hf-mirror.com
ExecStart=/opt/embedding-server/venv/bin/python3 /opt/embedding-server/server.py
Restart=on-failure

[Install]
WantedBy=default.target
```

### 3.2 aiduMEM 本体

```bash
mkdir -p ~/.hermes/aidumem-v204 && cd ~/.hermes/aidumem-v204
python3 -m venv venv
venv/bin/pip install aidumei    # 以项目实际包名为准；或按其官方安装文档
```

`.env`（放部署目录，systemd 自动加载）关键项模板：

```ini
# LLM：走第 2 章 10Router（全离线纪律：不直连任何云 API）
AIDUMEM_LLM_BASE=http://<内网IP>:20128/v1
AIDUMEM_LLM_MODEL=<你的记忆提炼模型组合名>
AIDUMEM_LLM_KEY=<10Router令牌>
# 嵌入：走本地 embedding-server
AIDUMEM_EMBED_BASE=http://127.0.0.1:8769/v1
AIDUMEM_EMBED_MODEL=e5-large
# rerank：本机决策为停用（9-04 决策），留空即关
```

用户级单元 `~/.config/systemd/user/aiduMEM.service`：

```ini
[Unit]
Description=aiduMEI v20.4 (Memory & Wisdom Engine)
After=network.target embedding-server.service

[Service]
WorkingDirectory=%h/.hermes/aidumem-v204
EnvironmentFile=%h/.hermes/aidumem-v204/.env
ExecStart=%h/.hermes/aidumem-v204/venv/bin/python api_server.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now embedding-server aiduMEM
```

### 3.3 接入 Hermes

Hermes 配置中把记忆 provider 指向 aiduMEM 的 MCP/HTTP 端点（:8767），此后对话自动沉淀与召回，无需手工搬记忆。

## 4. 配置

- 记忆提炼模型：选便宜快速的组合（提炼高频调用，旗舰模型纯浪费）；
- 全离线纪律：LLM 与 embedding 都必须本地/自托管路由内解决；
- 版本升级：新目录并行部署（aidumem-v205…），数据迁移按官方工具，旧目录保留可秒回滚。

## 5. 数据重建

- 记忆库：空库启动，随对话自动生长（可换皮核心：不迁移历史记忆）；
- 事实库/人设基座：使用中逐步重建；
- 备份对象：部署目录下的 SQLite/向量库文件（升级前必备份）。

## 6. 服务联动

- 依赖：2（提炼 LLM）、3.1（本地 embedding）、0（venv）；
- 被依赖：3（Hermes 记忆管道）；
- embedding 挂了的表现：入库/检索报连接错误，aiduMEM 本体不倒。

## 7. 验证

```bash
curl -s http://127.0.0.1:8769/health || curl -s http://127.0.0.1:8769/    # embedding 活着
systemctl --user is-active aiduMEM embedding-server
# 记忆闭环验证：对 Hermes 说一件关于你的事实 → 新会话提问 → 能召回即通
```

## 8. 升级与回滚

- 备份 `~/.hermes/aidumem-v204/` 数据文件 → 新版本并行目录部署 → 迁移脚本切换 → 旧目录保留；
- 回滚 = systemd 单元 WorkingDirectory 指回旧目录 + restart。
