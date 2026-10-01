---
title: UCloud 洛杉矶 VPS 代理架构与全景运维档案
category: projects
status: active
updated: 2026-10-01
tags: [proxy, ucloud, hysteria2, sing-box, warp, infrastructure, ai-infra]
---

# 🌐 UCloud 洛杉矶 VPS 代理架构与全景运维档案

> **文档定位**：全量还原 UCloud 洛杉矶节点（`107.150.103.84`）当前实际运行的代理架构、协议类型、服务编排、配置文件、自研代码、防护机制及与家庭中枢的联动关系，作为后续架构优化与演进的基准蓝本。

---

## 一、 主机基础设施与网络环境基线

### 1.1 资产与硬件概况
- **主机标识**：`10-11-8-204`（UCloud 洛杉矶轻量/云主机）
- **公网 IP**：`107.150.103.84`（美西洛杉矶）
- **内网 IP**：`10.11.8.204/16`（网关：`10.11.0.1`）
- **操作系统**：Ubuntu 24.04 LTS (`Linux 6.8.0-31-generic x86_64`)
- **运维权限**：`ubuntu` 账户（免密 `sudo` 提权），配置 SSH Ed25519 密钥互信（密钥路径：`~/.ssh/ucloud_la_node`）
- **资费与配额**：首年 ¥90 优惠机型，**月度出网流量配额 600 GB**（超额停机/高昂计费风险）

### 1.2 系统网络与内核参数基线（2026-10-01 调优生效）
| 参数项 | 当前实际值 | 调优前基线 | 状态评估与调优成果 |
|---|---|---|---|
| `net.ipv4.tcp_congestion_control` | **`bbr`** | `cubic` | ✅ **全面激活 BBR 拥塞控制算法**，极大提升跨国弱网抗丢包吞吐能力 |
| `net.core.default_qdisc` | **`fq`** | `pfifo_fast` | ✅ 升级为 **Fair Queueing (fq)**，实现纳秒级数据包公平调度 |
| IPv4/IPv6 路由策略 | **`precedence ::ffff:0:0/96 100`** | 默认全栈双栈 | ✅ **根除 IPv6 黑洞超时**，Google 首包响应延迟由 3.1s 暴降至 **82ms** |
| 防火墙与防爆破 | UFW 未激活，纯 iptables | - | fail2ban 纳管 SSH 22 端口，持续封禁恶意 IP |

---

## 二、 运行中服务与端口监听拓扑

### 2.1 网络端口分配总览
```
                                 [外部访问流量 / 家庭服务器请求]
                                                │
         ┌──────────────────────────────┬───────┴──────────────────────┬────────────────────────┐
         ▼ (UDP 443)                    ▼ (TCP 443)                    ▼ (TCP 8443)             ▼ (TCP 22)
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐     ┌──────────────────┐
│  Hysteria v2     │           │  sing-box v1.14  │           │  SNI Proxy       │     │  OpenSSH Server  │
│  (Hysteria2协议) │           │  (VLESS-Reality) │           │  (自研 Python)   │     │  (fail2ban保护)  │
│  UDP 高性能中继  │           │  TCP 伪装通道    │           │  GitHub 加速专用 │     └──────────────────┘
└────────┬─────────┘           └────────┬─────────┘           └────────┬─────────┘
         │                              │                              │
         │                              ├─ [OpenAI/ChatGPT] ──┐        │ (白名单放行)
         │                              │                     ▼ (SOCKS5 :40000)
         │                              │              ┌──────────────────┐
         │                              │              │ Cloudflare WARP  │
         │                              │              │ (MASQUE 住宅IP)  │
         │                              │              └────────┬─────────┘
         ▼                              ▼                       ▼
   [直连出网]                     [直连出网]              [WARP 出口出网]
```

### 2.2 详细监听套接字清单
| 协议 | 本地绑定地址 | 端口 | 对应进程 / 服务 | 角色与功能说明 |
|---|---|---|---|---|
| **UDP** | `0.0.0.0` | `443` | `hysteria` (PID 2407) | Hysteria 2 代理服务端（家庭服务器主力通道） |
| **TCP** | `0.0.0.0` | `443` | `sing-box` (PID 611643) | VLESS-Reality 代理服务端（备用防 UDP 阻断通道） |
| **TCP** | `0.0.0.0` | `8443` | `python3` (PID 611895) | `sni_proxy.py` SNI 透明反代（**已加白名单防盗**，保障 GitHub/Worker） |
| **TCP** | `127.0.0.1` | `40000` | `warp-svc` (PID 597620) | Cloudflare Zero Trust WARP SOCKS5 代理 |
| **TCP** | `127.0.0.1` | `39423` | `python3` (PID 4323) | `trafmon.py` 月度流量统计 HTTP API（供家庭端采集） |
| **TCP** | `0.0.0.0` | `22` | `sshd` (PID 1171) | 远程 SSH 管理端口，fail2ban 监控防护中 |

---

## 三、 核心代理组件与详细配置全景

### 3.1 Hysteria 2 服务（主力车道）
- **二进制路径**：`/usr/local/bin/hysteria` (Version: `v2.12.2`)
- **Systemd 单元**：`/etc/systemd/system/hysteria-server.service`
- **运行身份**：`hysteria:hysteria`，具备 `CAP_NET_ADMIN`, `CAP_NET_BIND_SERVICE`, `CAP_NET_RAW` 能力
- **配置文件路径**：`/etc/hysteria/config.yaml`
```yaml
listen: :443
tls:
  cert: /etc/hysteria/hysteria.crt
  key: /etc/hysteria/hysteria.key
auth:
  type: password
  password: 'Ud4etN83cZmVAxK7y6g0Nk1E'
masquerade:
  type: proxy
  proxy:
    url: https://www.bing.com
    respond: true
transport:
  type: udp
  udp:
    disablePathMTUDiscovery: false
obfs:
  type: salamander
  salamander:
    password: 'ipMbUdYJ7wOMtoN9DeNg'
```
- **特征分析**：
  1. 启用 `salamander` 混淆算法，抵抗运营商对 QUIC 流量的阻断与特征识别；
  2. 伪装站点为 `https://www.bing.com`；
  3. 证书为自签名证书（Subject: `CN=los-bnode`, 有效期至 2036 年）。

---

### 3.2 sing-box 服务（VLESS-Reality 通道 + WARP 链式分流）
- **二进制路径**：`/usr/bin/sing-box` (Version: `1.14.0`)
- **Systemd 单元**：`/usr/lib/systemd/system/sing-box.service`
- **运行身份**：`sing-box:sing-box`
- **配置文件路径**：`/etc/sing-box/config.json`
```json
{
  "log": {
    "level": "warning"
  },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-reality",
      "listen": "::",
      "listen_port": 443,
      "users": [
        {
          "uuid": "b0cbe1b2-bd93-4c5e-ba0e-7cbdf74801cc",
          "flow": "xtls-rprx-vision"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "www.microsoft.com",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "www.microsoft.com",
            "server_port": 443
          },
          "private_key": "2DEqOzXsSpFx9cIazx51LH_8A2MXusgPY4h6NpogY0k",
          "short_id": [
            "290d45f4468bab4d"
          ]
        }
      }
    }
  ],
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct"
    },
    {
      "type": "socks",
      "tag": "warp-out",
      "server": "127.0.0.1",
      "server_port": 40000
    }
  ],
  "route": {
    "rules": [
      {
        "domain_suffix": [
          "openai.com",
          "chatgpt.com",
          "oaistatic.com",
          "oaiusercontent.com",
          "sora.com"
        ],
        "domain_keyword": [
          "openai",
          "chatgpt"
        ],
        "outbound": "warp-out"
      }
    ],
    "final": "direct"
  }
}
```
- **特征分析**：
  1. 采用 XTLS-Vision 技术的 VLESS 协议，伪装目标为微软官网（`www.microsoft.com:443`）；
  2. **智能分流机制**：将所有 OpenAI / ChatGPT 相关域名智能路由至本地 WARP 客户端（`127.0.0.1:40000`），其余直连。
  3. **历史备份治理**：已将 `/etc/sing-box` 遗留的历史 `bak-*` 文件安全移至 `/root/backup-archive-20261001/`，目录严格保持单一事实源。

---

### 3.3 Cloudflare WARP 客户端（Clean IP 出口）
- **二进制路径**：`/bin/warp-svc` (warp-cli Version: `2026.7.1377.0`)
- **Systemd 单元**：
  - 核心进程：`/usr/lib/systemd/system/warp-svc.service`
  - 自启配置：`/etc/systemd/system/warp-proxy.service`（执行模式配置与端口绑定）
- **运行配置**：
  - 模式：`WarpProxy`（本地 SOCKS5 代理，监听端口 `40000`）
  - 隧道协议：`MASQUE` (HTTP/3)
  - 状态：`Connected`, `Network: healthy`
  - 落地出口：分配到 Cloudflare 洛杉矶机房原生 IP（如 `104.28.195.192`，Colo: LAX，Warp: on），纯净度极高。

---

### 3.4 自研服务一：SNI Proxy GitHub 加速与防护器 (`sni_proxy.py`)
- **脚本位置**：`/usr/local/bin/sni_proxy.py` (3.2 KB, Python 3)
- **Systemd 单元**：`/etc/systemd/system/sni-proxy.service`
- **监听端口**：`:::8443`
- **日志管理**：`/var/log/sni-proxy.log`（配有 `/etc/logrotate.d/sni-proxy` 自动切割轮转）
- **安全与加速策略**：
  1. 预设严格白名单：`github.com`, `githubusercontent.com`, `githubassets.com`, `workers.dev`, `pages.dev`, `cloudflare.com`, `sslip.io`；
  2. 保护机制：所有来自公网探测 `icanhazip.com`、`azenv.net` 等外部蹭流 IP **一律秒切断（BLOCK）**；合法 GitHub 加速请求秒级透传（ALLOW），彻底堵住每月 600G 的流量偷跑漏洞。

---

### 3.5 自研服务二：月度流量熔断探针 (`trafmon.py`)
- **脚本位置**：`/usr/local/bin/trafmon.py` (1.9 KB, Python 3)
- **Systemd 单元**：`/etc/systemd/system/trafmon.service`
- **运行身份**：`nobody`
- **监听端口**：`127.0.0.1:39423`（仅限本地环回）
- **接口路径**：`GET http://127.0.0.1:39423/traffic`
- **核心逻辑**：
  以微服务形式对外暴露 JSON 数据，汇报当月流量消耗（GB、已用百分比、重置日期与天数），直接对接家庭服务器的 `la-traffic-monitor.py` 看门狗守护。

---

## 四、 证书资产与系统优化沉淀

### 4.1 独立证书与 Let's Encrypt 资产
1. **Let's Encrypt 官方证书**：
   - 证书域名：`107-150-103-84.sslip.io`
   - 证书文件：`/etc/letsencrypt/live/107-150-103-84.sslip.io/fullchain.pem`
   - 私钥文件：`/etc/letsencrypt/live/107-150-103-84.sslip.io/privkey.pem`
   - 密钥类型：ECDSA，Certbot 定时轮转生效中（到期时间：2026-12-27）。
2. **Hysteria 专用自签证书**：
   - 路径：`/etc/hysteria/hysteria.crt` 与 `/etc/hysteria/hysteria.key`
   - 标识：`CN=los-bnode`

### 4.2 运维治理与资源瘦身
- **停止并禁用冗余进程**：已彻底停用 `ModemManager.service` 与 `multipathd.service`，降低 VPS 内存与 CPU 调度抖动；
- **临时与调试文件全盘清零**：清理 `/tmp/` 历史遗留的抓包和探测临时文件，系统盘恢复洁净。

---

## 五、 与家庭服务器的协同架构与分流策略

### 5.1 家庭端接入拓扑（在 `mihomo-next` 中）
家庭服务器通过当前主力代理中枢 `mihomo-next` 对接 UCloud 洛杉矶节点：
- **节点定义**：
  ```yaml
  - name: 洛杉矶UCloud
    type: hysteria2
    server: 107.150.103.84
    port: 443
    password: Ud4etN83cZmVAxK7y6g0Nk1E
    up: 50
    down: 80
    sni: los-bnode.local
    skip-cert-verify: true
    obfs: salamander
    obfs-password: ipMbUdYJ7wOMtoN9DeNg
  ```
- **核心分流车道（死钉洛杉矶UCloud）**：
  1. **Google 全家桶**（`GEOSITE,google`，含 Antigravity、Gemini API、Google 账户服务）：严禁漂移到机场订阅，100% 杜绝 400 地区不支持与 429 品牌风控；
  2. **10Router 海外大模型聚合网关**：包含 `openai.com`, `anthropic.com`, `openrouter.ai`, `deepseek.com`, `mistral.ai`, `groq.com`, `cline.bot` 等，全部直走洛杉矶独享原生 IP；
  3. **流量保护与熔断**：家庭端通过 `la-traffic-monitor.py` 严格监控 600G 配额。当月达到 98% 自动将车道平滑降级切换至机场备线，严禁 YouTube 等通用大流量经过 UCloud。
