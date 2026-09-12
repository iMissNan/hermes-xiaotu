# 8-YesPlayMusic音乐

> 一句话：白嫖流派的音乐中心——YesPlayMusic 自托管版 + 音乐源健康自动巡检，浏览器开箱即听。

## 1. 是什么

YesPlayMusic 是第三方网易云音乐播放器（高音质/无广告体验）。本机方案在官方镜像上**叠了一层实测补丁**（修播放链路 + 音源自动切换池），并配健康检查脚本定时巡检音源池——这就是"点开即播不跳歌"体验的来源。

## 2. 上游原址

- 项目：https://github.com/qier222/YesPlayMusic （MIT）
- 音乐 API 内核：`@neteasecloudmusicapienhanced/api`（镜像内自带）
- 镜像：`docker.1ms.run/junlongzzz/yesplaymusic`（国内源直拉；等价 Docker Hub 镜像亦可）
- **本机补丁**：随本仓发布 → `assets/yesplaymusic-patches/`（含说明见第 3.2 节）

## 3. 部署

### 3.1 容器

```bash
mkdir -p ~/.local/opt/yesplaymusic/{config,cookies}

docker run -d --name yesplaymusic \
  --restart unless-stopped \
  -p 8660:80 \
  -v ~/.local/opt/yesplaymusic/config:/usr/src/app/config \
  -v ~/.local/opt/yesplaymusic/cookies:/data_cookies \
  -e NETEASE_COOKIE="<你自己的网易云MUSIC_U cookie>" \
  docker.1ms.run/junlongzzz/yesplaymusic
```

> `MUSIC_U` cookie 获取：浏览器登录自己的网易云账号后从 Cookie 里复制（这是你的账号凭据，别用别人的）。

### 3.2 补丁重放（复刻同款体验的关键）

```bash
cd ~/.local/opt/yesplaymusic
# 从本仓补丁目录逐个 docker cp 挂进容器对应路径（映射表）：
#   nginx-default.conf → /etc/nginx/http.d/default.conf (ro)
#   server.js / option.js / apicache.js → .../api/{server.js,util/option.js,util/apicache.js} (ro)
#   playlist_detail.js / playlist_track_all.js / song_detail.js / song_url.js → .../api/module/ (ro)
#   modules/ → .../api/node_modules/@neteasecloudmusicapienhanced/unblockmusic-utils/modules (ro)
#   html/ → /usr/share/nginx/html (ro)
docker restart yesplaymusic
```

### 3.3 音源健康巡检（可选但推荐）

```bash
cp assets/yesplaymusic-patches/health-check.py ~/.local/opt/yesplaymusic/
# crontab -e 加入（每天 05:00 巡检音源池并自动切换）：
# 0 5 * * * /usr/bin/python3 ~/.local/opt/yesplaymusic/health-check.py >> ~/.local/opt/yesplaymusic/health-check.log 2>&1
```

## 4. 配置

- 音源池：`config/source-pool.json`（结构模板在补丁包内，填你自己可用的音源接口）；
- 巡检 API 地址环境变量 `YPM_HEALTH_API` 指向本机容器端口。

## 5. 数据重建

- 歌单：登录自己的账号自动带入（cookie 即身份）；
- 播放历史/收藏在网易云账号侧，本机只缓存。

## 6. 服务联动

- 依赖：0（Docker）、1（音源探测走 7894）；
- 被 6（Homarr 入口卡）、11（Kuma 监控播放可用性）。

## 7. 验证

```bash
docker ps | grep yesplaymusic
curl -sI http://<内网IP>:8660 | head -1
# 功能验证：打开界面 → 随机点 3 首热门歌 → 连播不跳歌（补丁生效的标志）
```

## 8. 升级与回滚

- 镜像更新后**补丁必须重放**（容器层文件随镜像重置）——第 3.2 节命令重跑一遍；
- 回滚 = 退镜像 tag + 重放对应版本补丁；cookies 卷不动。
