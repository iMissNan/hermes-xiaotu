# 7-MarsTV云影院

> 一句话：全家人的"腾讯视频"——采集+聚合全网影视源的网页影院，海报墙点开即播，还自带 TVBox 蜘蛛接口给电视 App 用。

## 1. 是什么

MarsTV 是自研影视中台（对内开源，源码随本仓发布）：FastAPI 后端 + nginx 静态前端 + drpy2 蜘蛛引擎三层。它定时扫描采集源、维护片库健康（坏源自动下线）、对外提供网页影院和 TVBox 接口。

## 2. 上游原址

- **自研组件**：源码入仓 → `assets/martv-source.tar.gz`（app+scripts+spider，解包即用）
- 运行时依赖：Python venv（FastAPI/uvicorn）、Node23（蜘蛛引擎 drpy2）、nginx（本机系统自带）
- 影视采集源：自己配置的第三方接口（本仓不携带任何采集源地址）

## 3. 部署

```bash
# 解包源码
sudo mkdir -p /opt/martv && sudo chown $USER /opt/martv
tar -xzf assets/martv-source.tar.gz -C /opt/martv --strip-components=1
cd /opt/martv && mkdir -p data logs

# 后端 venv
python3 -m venv venv
venv/bin/pip install -r app/requirements.txt 2>/dev/null || venv/bin/pip install fastapi uvicorn httpx

# 蜘蛛引擎依赖
cd spider && npm install --omit=dev && cd ..

# 前端：app/static 随源码自带（nginx 托管）
```

三个用户级单元（`~/.config/systemd/user/`）：

```ini
# martv-backend.service —— API 后端 :8090
[Service]
WorkingDirectory=/opt/martv/app
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/martv/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8090 --workers 1
Restart=on-failure
```

```ini
# martv-spider.service —— 蜘蛛引擎 :8095
[Service]
WorkingDirectory=/opt/martv/spider
Environment=NODE_ENV=production
ExecStart=%h/.local/opt/node23/bin/node engine_server.mjs
Restart=on-failure
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now martv-backend martv-spider
```

nginx 站点 `/etc/nginx/sites-enabled/martv`（核心：静态托管 + 强缓存策略，完整模板随源码 `app/nginx-martv.conf` 提供）：

```nginx
server {
    listen 8082;
    root /opt/martv/app/static;
    index index.html;
    location /api/ { proxy_pass http://127.0.0.1:8090; }
    location ~* \.(js|css|png|jpg|webp|svg|woff2?)$ { expires 7d; }
    location = /sw.js { add_header Cache-Control "no-cache"; }
}
```

```bash
sudo ln -sf /opt/martv/app/nginx-martv.conf /etc/nginx/sites-enabled/martv
sudo nginx -t && sudo systemctl reload nginx
```

## 4. 配置

- 采集源：源码内配置文件模板给出结构，**填你自己找的采集接口**；
- 定时任务四件套（片库更新/探索/热度/巡逻，crontab）：

```cron
5-59/30 * * * * flock -n /tmp/martv-update.lock  nice -n 19 /opt/martv/venv/bin/python /opt/martv/app/source_engine.py update  >> /opt/martv/logs/cron.log 2>&1
17 */6 * * *    flock -n /tmp/martv-explore.lock nice -n 19 /opt/martv/venv/bin/python /opt/martv/app/source_engine.py explore >> /opt/martv/logs/cron.log 2>&1
23 */6 * * *    flock -n /tmp/martv-hot.lock     nice -n 19 /opt/martv/venv/bin/python /opt/martv/app/hot_engine.py refresh     >> /opt/martv/logs/cron.log 2>&1
10 12 * * *     flock -n /tmp/martv-patrol.lock  nice -n 19 /opt/martv/venv/bin/python /opt/martv/app/source_engine.py patrol  >> /opt/martv/logs/cron.log 2>&1
```

- 性能参数：后端 CPU 限核 `CPUQuota=50%`、预热 TTL 3600s（低配机实测稳定值）。

## 5. 数据重建

- 片库（data/ 下 SQLite）：**不用迁移**——起服务后 cron 自动扫描采集源重建，一晚片库成型；
- 采集源配置：填自己的接口（可换皮核心）。

## 6. 服务联动

- 依赖：0（nginx/venv/node）、1（采集源探测可能需出外网，走 7894）；
- 被依赖：11（Uptime Kuma 监控片库健康）、6（Homarr 入口卡）；
- TVBox/影视仓 App 用户：蜘蛛接口 `http://<内网IP>:8095/`（ spiders 协议不通用，App 侧需支持 drpy2）。

## 7. 验证

```bash
systemctl --user is-active martv-backend martv-spider
curl -sI http://<内网IP>:8082 | head -1          # 前端门通
curl -s http://127.0.0.1:8090/docs | head -1     # API 活着
# 功能验证：前端海报墙有片 → 点开即播
```

## 8. 升级与回滚

```bash
# 升级：重新打包覆盖 /opt/martv/{app,spider,scripts}（data/logs 不动）
systemctl --user restart martv-backend martv-spider && sudo systemctl reload nginx
```

- 片库坏了：停 cron → 删 data/ 库 → 跑一次 update 重建（片库是可再生资源）；
- 版本回滚：tar 包覆盖回去重启三件套。
