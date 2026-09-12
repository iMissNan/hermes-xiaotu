# 6-Homarr导航面板

> 一句话：全家服务的统一门厅——所有服务的入口卡片、状态灯、快捷跳转都在这一屏。

## 1. 是什么

Homarr 是自托管仪表盘：把全部服务（10Router/Homarr/MarsTV/_obsidian-web_/监控…）做成可点的卡片，带在线状态探测。家庭系统的日常入口——手机/平板收藏夹只需要一个地址。

## 2. 上游原址

- 项目：https://github.com/homarr-labs/homarr （AGPL-3.0，活跃）
- 镜像：`ghcr.io/homarr-labs/homarr:latest`

## 3. 部署

```bash
mkdir -p ~/.local/opt/homarr/configs ~/.local/opt/homarr/icons

docker run -d --name homarr \
  --restart unless-stopped \
  -p 7575:7575 \
  -v ~/.local/opt/homarr/configs:/app/data/configs \
  -v ~/.local/opt/homarr/icons:/app/public/icons \
  -e DB_URL=/appdata/db/db.sqlite \
  -e AUTH_PROVIDERS=credentials \
  ghcr.io/homarr-labs/homarr:latest
```

| 参数 | 说明 |
|---|---|
| `/app/data/configs` | 布局/卡片配置（JSON，可备份可迁移） |
| `/app/public/icons` | **自托管图标库**——同源图标，禁外链 CDN |
| `AUTH_PROVIDERS=credentials` | 账号密码登录 |

## 4. 配置

- **图标铁律**：维护者网络环境下外网 CDN 图标不可达，所有卡片图标放 `icons/` 目录用同源路径引用；复刻者若外网畅通可自定义，但同源方案在任何网络下都成立；
- 卡片分类用 empty 容器型分组（v1 行为：预设分类组会导致布局错乱）；
- 首次进入：注册自己的账号 → 编辑模式拖卡片 → 每卡填 `http://<内网IP>:<端口>`。

## 5. 数据重建

- 卡片布局：照第 7 节验证清单里的服务清单逐卡添加（半小时活）；
- SQLite 库（docker volume `/appdata`）内含账号与布局，备份=备该卷。

## 6. 服务联动

- 依赖：0（Docker）；
- 被依赖：全员的入口（验收清单第 13 章以此为一站式检查页）。

## 7. 验证

```bash
docker ps | grep homarr
curl -sI http://<内网IP>:7575 | head -1
# 功能验证：登录后看到 ≥8 张卡片且状态灯全绿（对照 DEPLOYMENT.md 服务一览表）
```

## 8. 升级与回滚

```bash
docker pull ghcr.io/homarr-labs/homarr:latest
docker rm -f homarr   # 重跑第 3 节；configs/icons 卷持久化
```

布局异常时：`~/.local/opt/homarr/configs` 里的 JSON 可手工修正或回滚备份。
