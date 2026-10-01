# aiduMEM v10.1 → v14.0 Aegis 升级实例（2026-08-01）

## 变更全貌（升级前必须知道的）

| 项目 | v10.1 Clotho（旧） | v14.0 Aegis（新） |
|------|-------------------|-------------------|
| 包目录 | `dumem/` | `ducky/`（改名！） |
| 入口 | `run.py` | `api_server.py` |
| Python | 3.11 | 3.12（`apt install python3.12-venv`） |
| mem0 | 0.x | **mem0ai==2.0.5**（大版本） |
| 数据文件 | `data/fts/fts.db`、`data/core_memory.db`、`data/qdrant/` | `data/facts.db`、`data/text_fts.db`、`data/observations.db`、`data/salience.db`、`data/qdrant/` |
| 建表 | 手工部署 | `ducky/schema_bootstrap.py` 首次启动自动建（IF NOT EXISTS，对既有库 no-op） |
| vault 索引 API | `POST /api/vault/index` | `POST /facts/add?category=&fact_key=&fact_value=&source=`（**query 参数**，POST 方法） |
| 健康端点 | `/health` 含 text_fts/fts_count | `/health` 结构不同（无这些字段）；`/api/memory/health` 已删除（404） |
| 检索 | `/facts/search`（LIKE 子串） | `/facts/search`（facts_recall，LIKE + category 候选） |
| mem0 检索 | — | `POST /search`（向量召回，有相关性阈值——精确词才命中，语义近邻可能被过滤） |
| 默认监听 | 0.0.0.0 | **127.0.0.1**（要外部访问显式 `AIDUMEM_HOST=0.0.0.0`） |

## 数据迁移要点

- **facts 与 mem0 是两套体系**：`/facts/add` 写 facts 表（text_fts 的 memories 表 **不同步**，fts_memories 探针=text_fts.db memories 表，常为 0 属已知语义）；`/add`（mem0）写 qdrant 向量
- 旧库迁移：从备份 `data/fts/fts.db` 的 `fact_metadata` 表读 `content/category/source` → 过滤测试数据 → 逐个 `POST /facts/add` 重建
- vault（markdown 数据源）重索引：`vault-indexer-v14.py`（扫描 ALLOWED_PREFIXES 目录 → /facts/add）

## SiliconFlow API 坑（mem0 配置）

- **embeddings 不接受 `dimensions` 参数** → 400 `code 20015`：mem0 配置里 `embedder.config.embedding_dims` 会转成请求的 dimensions → **必须删掉**（bge-m3 默认 1024 维）
- 模型必须全名：`BAAI/bge-m3`（简写 bge-m3 → 400 Model not exist）；LLM 模型用 `Qwen/Qwen2.5-72B-Instruct` 实测 200（`deepseek-ai/DeepSeek-V3` 429 限流、`deepseek-chat` 不存在）
- LLM 与 embedder 可统一 SiliconFlow（一个 key 全搞定）；opencode 网关 key（旧 .env 的 OPENAI_API_KEY）可能已失效且其模型名是 minimax/kimi 系列
- 参数排查法：逐个加参数 curl 上游（input_type/dimensions/encoding_format）定位 400 根因

## 本机部署最终形态

- `~/.hermes/aidumem-v14/`：venv（python3.12 + mem0ai 2.0.5）+ api_server.py + config/（`mem0_config_local.json` + `.env`）
- systemd 用户服务 `aiduMEM.service`：WorkingDirectory=v14 目录、EnvironmentFile=v14/.env、ExecStart=venv/bin/python api_server.py
- cron：vault 索引 `vault-indexer-v14.py`（每 6h）+ 健康日报（调 /health + /facts + /facts/search，旧 /api/memory/health 已删）
- 测试数据清理：`POST /facts/expire?fact_id=N` 标记过期（24h 后自动清）而非硬删；mem0 测试记忆用 `POST /delete {memory_id}`
