# 11-UptimeKuma监控

> 一句话：全系统的体检中心——每个服务一条心跳，挂了第一时间知道（而不是用的时候才发现）。

## 1. 是什么

Uptime Kuma 是自托管拨测监控：HTTP/TCP/关键词探测 + 状态页 + 通知（Telegram/ntfy 等）。本机用它盯影视源健康和全部服务入口。

## 2. 上游原址

- 项目：https://github.com/louislam/uptime-kuma （MIT，活跃）
- 部署形态：裸机（用户级 systemd），`~/.local/opt/uptime-kuma`（git clone + npm）

## 3. 部署

```bash
mkdir -p ~/.local/opt && cd ~/.local/opt
git clone https://github.com/louislam/uptime-kuma.git
cd uptime-kuma
npm run setup          # 官方安装脚本（装依赖+前端构建）
```

用户级单元 `~/.config/systemd/user/uptime-kuma.service`：

```ini
[Unit]
Description=Uptime Kuma - 自托管监控看板
After=network.target

[Service]
WorkingDirectory=%h/.local/opt/uptime-kuma
Environment=UPTIME_KUMA_PORT=8081
Environment=NODE_ENV=production
ExecStart=%h/.local/opt/node23/bin/node server/server.js
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now uptime-kuma
```

## 4. 配置

首次打开 `http://<内网IP>:8081` 注册管理员，然后按下面的**必监清单**加监控（对齐 DEPLOYMENT.md 服务一览）：

| 监控名 | 类型 | 目标 | 间隔 |
|---|---|---|---|
| 10Router | HTTP | `http://<内网IP>:20128` | 60s |
| MarsTV 前端 | HTTP | `http://<内网IP>:8082` | 60s |
| MarsTV API | HTTP | `http://127.0.0.1:8090/docs` 关键词 `FastAPI` | 120s |
| 音乐中心 | HTTP | `http://<内网IP>:8660` | 300s |
| 知识库 Web | HTTP | `http://<内网IP>:8083` | 300s |
| 导航面板 | HTTP | `http://<内网IP>:7575` | 300s |
| 密码台账 | HTTP | `https://<你的域名>:8445` | 300s |
| MariaDB | TCP | `127.0.0.1:3306` | 300s |

通知渠道建议配 ntfy/Telegram（按你自己有的来）。

## 5. 数据重建

监控项按上表手工重建（10 分钟活）；数据目录 `~/.local/opt/uptime-kuma/data`（SQLite），备份=拷目录。

## 6. 服务联动

- 依赖：0（node）；被 6（Homarr 可挂 Kuma 状态卡）；
- 监控对象挂了 → 通知渠道报警 → 对应 replication 指南的"第 8 节"排障。

## 7. 验证

```bash
systemctl --user is-active uptime-kuma
curl -sI http://<内网IP>:8081 | head -1
# 功能验证：必监清单 8 条全部"绿"→ 手动停一个服务看告警是否触发 → 再启回来
```

## 8. 升级与回滚

```bash
cd ~/.local/opt/uptime-kuma && git fetch && git checkout <新版本tag> && npm run setup --force
systemctl --user restart uptime-kuma
```

升级前备份 `data/`；回滚=checkout 回旧 tag 重启。
