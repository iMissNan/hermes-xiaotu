# 9-TokenHub

> 一句话：AI 令牌资产管家——多平台 token/账号的签到、余额与用量看板，和第 2 章 10Router 的渠道管理形成"资产→供给"闭环。

## 1. 是什么

TokenHub（SimpleHub 系）管理分散在各白嫖平台的 API 令牌：集中看余额/到期、自动签到保活、用量统计。本机生产形态为**裸机 node 服务**（`/opt/tokenhub`，系统级 systemd），:20129。

## 2. 上游原址

- 镜像形态（备用）：https://ghcr.io/jwy87/simplehub （本机容器已停用，裸机为现行形态）
- 裸机源码：`/opt/tokenhub`（node18 运行时）
- 依赖：MariaDB（本机 :3306 仅回环，供其数据存储）

## 3. 部署

### 3.1 数据库（前置）

```bash
sudo apt install -y mariadb-server
sudo mysql -e "CREATE DATABASE tokenhub CHARACTER SET utf8mb4;"
sudo mysql -e "CREATE USER 'tokenhub'@'localhost' IDENTIFIED BY '<自行生成数据库口令>';"
sudo mysql -e "GRANT ALL ON tokenhub.* TO 'tokenhub'@'localhost';"
```

### 3.2 应用本体

```bash
sudo mkdir -p /opt/tokenhub && sudo chown $USER /opt/tokenhub
# 从上游获取源码/发行包到 /opt/tokenhub（simplehub 发行版）
cd /opt/tokenhub
npm install --omit=dev
```

系统级单元 `/etc/systemd/system/tokenhub.service`：

```ini
[Unit]
Description=TokenHub (simplehub) token asset manager
After=network.target mariadb.service

[Service]
User=<你的用户>
WorkingDirectory=/opt/tokenhub
Environment=PORT=20129
Environment=NODE_ENV=production
ExecStart=/home/<你>/.local/opt/node23/bin/node src/server.js
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now tokenhub
```

## 4. 配置

- 数据库连接、鉴权开关（`SKIP_AUTH` 仅限纯内网用，复刻者自行权衡）等经环境变量/配置文件；
- 平台账号与 token 在面板内逐个添加（你的资产你做主）。

## 5. 数据重建

- 平台 token/账号：面板逐条录入（敏感凭据不入仓不入档）；
- MariaDB 库随用随长，备份=mysqldump。

## 6. 服务联动

- 依赖：0（node/MariaDB）、2（如需 AI 摘要/通知可走 10Router）；
- 被 6（Homarr 入口卡）；与 2 的关系：TokenHub 管"粮仓资产"，10Router 管"做饭供给"。

## 7. 验证

```bash
systemctl is-active tokenhub mariadb
curl -sI http://<内网IP>:20129 | head -1
# 功能验证：面板可见已录入平台 → 手动触发一次签到 → 状态更新
```

## 8. 升级与回滚

```bash
cd /opt/tokenhub && git pull 2>/dev/null || 重新下载发行包覆盖
npm install --omit=dev && sudo systemctl restart tokenhub
```

升级前 `mysqldump tokenhub > ~/tokenhub-backup-$(date +%m%d).sql`；回滚=还原代码目录+重启。
