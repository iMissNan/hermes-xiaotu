# 手机 PAC 智能分流与免关代理双重防呆架构设计规格

- **日期**：2026-10-01
- **作者**：常驻小兔 🐰
- **状态**：待评审（Draft for Review）
- **目标**：彻底解决手机 WiFi 挂代理时“大文件下载误烧海外独享配额”、“BT/迅雷版权封号风险”、“忘记关代理导致国内降速卡顿”三大痛点，实现用户零感知、终生免手动开关代理的智能化体验。

---

## 1. 架构核心思想：双层防呆体系

整个体系分为**客户端源头智能分流（第一道防线）**与**服务器底层物理截流（第二道防线）**：

```
                             [手机发起所有网络请求]
                                       │
                                       ▼
                       【第一道防线：手机本地 PAC 引擎】
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
    [命中海外受阻域名名单]                               [国内大厂/游戏/网盘/迅雷/随机网站]
   (Google/AI/GitHub/X/YouTube)                                   │
            │                                                     │
            ▼ (仅受限流量走代理)                                    ▼ (95% 日常大流量)
  [手机发送给 192.168.1.70:7892]                             [手机本地直接走光猫千兆]
            │                                              ★ 0% 经过服务器
            ▼                                              ★ 0% 消耗海外配额
 【第二道防线：服务器底层硬核兜底】                           ★ 满血跑满 1000M 带宽
    ├─ 1. Google Drive 剥离洛杉矶 -> 走免费池               ★ 原生满血支持 UDP/QUIC
    └─ 2. 海外 BT/Tracker 连接 -> 严禁出海 REJECT
```

---

## 2. 组件详细规格设计

### 2.1 组件一：PAC 智能分流脚本 (`proxy.pac`)
- **文件位置**：`/var/www/html/proxy.pac`
- **访问地址**：
  - 内网直达：`http://192.168.1.70:8080/proxy.pac`
  - 域名直达：`https://home.nanshark.ccwu.cc:8443/proxy.pac`
- **MIME 契约**：`application/x-ns-proxy-autoconfig`
- **判别优先级（从高到低）**：
  1. **内网与局域网段**：`192.168.*`, `10.*`, `172.16.*`, `127.*`, `100.64.*`, `*.local`, `*.lan` ➔ `DIRECT`
  2. **国内大厂与生活娱乐**：微信、QQ、淘宝、天猫、支付宝、京东、美团、抖音、快手、网易、百度、B站、微博、知乎等 ➔ `DIRECT`
  3. **大文件下载与游戏平台**：迅雷、百度网盘、阿里云盘、夸克网盘、Steam、Epic Games、WeGame、TapTap、各大游戏 CDN ➔ `DIRECT`
  4. **受限海外服务清单（智能代理）**：
     - AI 平台：`openai.com`, `anthropic.com`, `claude.ai`, `openrouter.ai`, `groq.com`, `deepseek.com`, `cline.bot`, `qoder.com` 等
     - 开发者生态：`github.com`, `githubusercontent.com`, `ghcr.io`, `docker.com`, `huggingface.co` 等
     - 海外核心媒体与搜索：`google.com`, `youtube.com`, `twitter.com`, `x.com`, `t.me`, `telegram.org`, `wikipedia.org` 等
     ➔ `PROXY 192.168.1.70:7892; DIRECT`
  5. **兜底法则（防呆精髓）**：
     `return "DIRECT";`
     **任何未收录的冷门小站、生僻网站、随机下载站，默认全走手机本地直连！绝不送往代理服务器！**

---

### 2.2 组件二：Nginx PAC 托管与自动刷新
- 在 `/etc/nginx/sites-available/rabbit-proxies.conf` 的 `8080` 端口服务器增加针对 `.pac` 的类型响应头与缓存控制：
  ```nginx
  location = /proxy.pac {
      add_header Content-Type "application/x-ns-proxy-autoconfig; charset=utf-8";
      add_header Cache-Control "no-cache, must-revalidate";
  }
  ```
- 在安全网关 `8443` 端口增加代理映射，方便手机在 Tailscale 下或内网任意形式访问。

---

### 2.3 组件三：服务器端底层双重保险（Mihomo 规则协同）
即使其他设备误用了全局手动代理，服务器也能自动兜底保护：
1. **防线 A：剥离谷歌网盘独享出站**
   在 `config.yaml` 的 `GEOSITE,google` 之前插入：
   ```yaml
   - DOMAIN-KEYWORD,drive.google,节点选择
   - DOMAIN-SUFFIX,googleusercontent.com,节点选择
   ```
   大文件网盘滚去走免费池，洛杉矶 600G 额度只留给文字 API 与核心认证。
2. **防线 B：BT / PT 严禁出海**
   ```yaml
   - GEOSITE,category-pt,REJECT
   - DOMAIN-KEYWORD,torrent,REJECT
   - DOMAIN-KEYWORD,tracker,REJECT
   ```
   杜绝海外版权投诉封号。

---

## 3. 验收标准与验证方案

1. **PAC 文件端到端可达性验证**：
   - `curl -I http://192.168.1.70:8080/proxy.pac` 返回 `HTTP 200`，且 `Content-Type: application/x-ns-proxy-autoconfig`。
2. **分流逻辑单体测试（模拟执行）**：
   - 模拟 `FindProxyForURL("http://www.baidu.com", "www.baidu.com")` ➔ 返回 `DIRECT`
   - 模拟 `FindProxyForURL("http://down.gamersky.com/game.iso", "down.gamersky.com")` ➔ 返回 `DIRECT`
   - 模拟 `FindProxyForURL("https://api.openai.com/v1", "api.openai.com")` ➔ 返回 `PROXY 192.168.1.70:7892`
   - 模拟 `FindProxyForURL("http://random-unknown-site.xyz/20G.zip", "random-unknown-site.xyz")` ➔ 返回 `DIRECT`（零漏网防呆生效）
3. **手机端真实接入验证**：
   - 手机 WiFi 代理设置为“自动”，填入 PAC 地址；
   - 访问 `www.google.com` 正常打开；
   - 手机下载测试文件，监控服务器 7892 端口无流量飙升，确认完全走手机本地直连。

---

## 3. 审计补遗（2026-10-01 晚 · 第三方审计定案）

> 本节由独立审计轮补录，修正原稿两处盲点并记录收尾实测。

### 3.1 硬伤一：GEOSITE,cn 天生不含 snssdk 系（已修复）
- **根因**：上游 v2fly 数据 geolocation-cn 引用 bytedance 标签时带 @-!cn 属性（仅收非中国域名），故 GEOSITE,cn 不含 snssdk.com / zijieapi.com 等国内主域。审计实测 6 小时内 125 条抖音国内域走 MATCH 误出海。
- **修复**：规则区手工补 DOMAIN-SUFFIX,snssdk.com / zijieapi.com / zjcdn.com → DIRECT（commit b34a7f9，已推 GitHub）。端到端实测 aweme.snssdk.com 经 7892 → using DIRECT（59ms）。

### 3.2 硬伤二：GEOIP,CN,no-resolve 对手机流量结构性失效（定性保留）
- fake-ip 模式下手机 CONNECT 带纯域名，规则按域名匹配；no-resolve 又禁止解析成 IP —— 域名匹配不到、IP 不许查，两头堵死，该规则对局域网代理设备永不命中。
- **决策**：保留不删。服务器本机流量（先解析后连）仍受其保护；局域网设备的国内兜底由 DOMAIN-SUFFIX 白名单补位。属规则组合的先天约束，非配置缺陷。

### 3.3 其余收尾记录
- config.yaml.bak-pre-dnsfix 已删除（版本管理归 git，遵守禁 .bak 铁律）。
- 热载验证注意：DOMAIN-SUFFIX 纯文本规则不走 GeoSite 加载器、无专属 journalctl 日志行，验证须查 :9090/rules API（运行时 93 条含新规则）。
- 探活矩阵 6 项全绿；手机已于当日 16:29 切换 PAC，直连流量不经服务器符合预期。
