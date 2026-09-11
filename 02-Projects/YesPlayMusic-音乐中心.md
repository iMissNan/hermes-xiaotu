---
title: YesPlayMusic 音乐中心
category: project
status: active
created: 2026-09-11
updated: 2026-09-11
tags: [music, media, yesplaymusic, ypm]
aliases: [YesPlayMusic, YPM, 音乐播放器]
---

# 🎵 YesPlayMusic 音乐中心

> 💡 **核心定位**：高颜值自托管网易云音乐网页版，集成自动解灰（UnblockNeteaseMusic），专为维护者定制流行/热歌体验。

---

## 1. 核心访问入口与定位
- **局域网/公网入口**：`http://<你的域名>:8660/`
- **认证凭据**：统一口令 `<统一口令>`，详见 [[03-Areas/账号与服务密码管理基线]]
- **部署类型**：Docker 容器（名称：`yesplaymusic`）

## 2. 音乐体验与避坑铁律
- **点开即播铁律**：厌恶口水歌/买榜歌，偏好汽水音乐与抖音热歌高品质曲库；
- **解灰插件避坑**：维护者 Windows 电脑（lqdn9sp）浏览器不可残留第三方代理插件，避免引发 YPM 串流跳歌。

## 3. 极简运维指令
- 重启容器：`docker restart yesplaymusic`
- 查看日志：`docker logs -f --tail 50 yesplaymusic`

## 4. 上下游拓扑关联
- 统一网络入口：[[03-Areas/家庭服务器网络拓扑与DNS解析]]

---
## 5. 变更历史（原位追加）
- `2026-09-11`：修正 Homarr 存活探针并固化主卡。
