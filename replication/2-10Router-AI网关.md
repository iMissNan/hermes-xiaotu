# 2-10Router-AI网关

> 一句话：全系统唯一的 LLM 出口——聚合各家上游（官方 API、白嫖渠道、兜底模型），对内提供 OpenAI 兼容接口与智能故障切换。所有 AI 服务（Hermes/aiduMEM/AO）都从它拿模型。

## 1. 是什么

10Router 是 9Router 的精简优化分支：一个带 Web 面板的 AI 网关，负责渠道管理、密钥保管、模型组合（失败自动切下一个）、用量统计。家庭 AI 系统里它处于**正中心**：上游接各家 LLM，下游服务一切。

## 2. 上游原址

- 项目仓库：https://github.com/techysy/10router （MIT，活跃维护）
- Docker 镜像：`ghcr.io/techysy/10router:latest`
- npm 包（裸机方式）：`npm i -g @techysy/10router`（本文以 Docker 为准）

## 3. 部署

```bash
docker run -d --name 10router \
  --restart unless-stopped \
  -p 20128:20128 \
  -v ~/.10router:/app/data \
  -e PORT=20128 \
  -e DATA_DIR=/app/data \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -e KEEP_ALIVE_TIMEOUT=120000 \
  -e STREAM_FIRST_CHUNK_TIMEOUT_MS=90000 \
  -e STREAM_STALL_TIMEOUT_MS=150000 \
  ghcr.io/techysy/10router:latest
```

| 参数 | 说明 |
|---|---|
| `-p 20128:20128` | 面板与 API 端口 |
| `-v ~/.10router:/app/data` | 全部持久化数据（SQLite 库/密钥/日志） |
| `KEEP_ALIVE_TIMEOUT` | 长连接保活 120s（LLM 长回复必需） |
| `STREAM_FIRST_CHUNK_TIMEOUT_MS` | 流式首包超时 90s（慢模型不误杀） |
| `STREAM_STALL_TIMEOUT_MS` | 流式停滞超时 150s（卡死自动断） |

首次打开 `http://<内网IP>:20128/` 注册管理员账号。

### 中国大陆网络增强（可选）

Google 系渠道（如 Antigravity）的 OAuth token 每小时刷新一次，直连 `oauth2.googleapis.com` 会被墙导致整点掉线 401。本仓提供两个实测补丁（`assets/10router-patches/`）：

**补丁 A：OAuth 刷新走代理**（`google-oauth-proxy.cjs`）

```bash
mkdir -p ~/.10router/patches
cp assets/10router-patches/google-oauth-proxy.cjs ~/.10router/patches/
# 重建容器时追加两个 env：
#   -e GOOGLE_TOKEN_PROXY=http://172.17.0.1:7892
#        （172.17.0.1=Docker 默认网桥=宿主机；7892=第 1 章的 AI 专用出口，不可用 7894）
#   -e NODE_OPTIONS=--require /app/data/patches/google-oauth-proxy.cjs
```

原理：预加载钩子只拦截 `oauth2.googleapis.com` 的请求走代理隧道，其余流量原样放行，代理挂了自动退回直连。

**补丁 B：聊天链路强制 strictProxy**（`strict-proxy.cjs`，一次性执行）

```bash
docker cp assets/10router-patches/strict-proxy.cjs 10router:/tmp/
docker exec 10router node /tmp/strict-proxy.cjs
docker restart 10router
```

原理：官方镜像的聊天链路代理失败会回落裸连并挂死；补丁强制 strictProxy（代理失败立即报错触发切换）。幂等，镜像升级后重打即可。

## 4. 配置

全部在 Web 面板完成：**渠道**（上游 API 地址+密钥）→ **模型**（映射与倍率）→ **组合**（多模型排序=故障切换顺序）。

组合设计模板（本机同款思路）：
1. 主力：白嫖/低价渠道的旗舰模型；
2. 备选：另一家渠道的强模型；
3. 兜底：必有（渠道全挂时系统仍可用）。

密钥只存于 `~/.10router/db/data.sqlite`，面板不回显明文。

## 5. 数据重建

- 渠道/模型/组合：面板手工重建（复刻者用自己的 API 密钥）；
- 数据库即身份：`~/.10router/db/data.sqlite`（含账号密码哈希），备份=拷目录；
- jwt-secret / machine-id（`~/.10router/` 下 64B 密钥文件）：首次启动自动生成，**不要拷贝别人的**。

## 6. 服务联动

- 依赖：第 1 章 7892 出口（Google 渠道刷新必需）；
- 被依赖：Hermes(3)、aiduMEM(4)、AO(12)、TokenHub(9) 的 LLM 流量全部走 `http://<内网IP>:20128/v1`；
- 出口线路纪律：Google 刷新只准 7892（稳定直连线路），烧错线路=整点断线。

## 7. 验证

```bash
docker ps | grep 10router                                  # 容器活着
curl -s http://<内网IP>:20128/api/health || echo "以面板为准"   # 入口可达（不同版本路径可能不同，以面板为准）
# 真链路验证：用面板里任意一个渠道的模型发一条测试对话
# 下游联动验证：在第 3 章 Hermes 里把 provider 指向 10Router 后跑一轮对话
docker logs --tail 30 10router                             # 无持续报错
```

## 8. 升级与回滚

```bash
docker pull ghcr.io/techysy/10router:latest
docker rm -f 10router
# 重跑第 3 节 docker run（数据卷在 ~/.10router，配置全保留）
# 升级后记得重打补丁 B（strict-proxy）
```

- 数据卷不动=回滚只退镜像；数据库自动快照在 `~/.10router/db/backups/`。
- 补丁 A 随数据卷常驻（patches/ 在 `~/.10router` 内），升级不影响。
