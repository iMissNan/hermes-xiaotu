# AdGuard Home 部署手册 · WO-1001 · 2026-10-01

## 零、一句话
192.168.1.70 裸装 AdGuard Home v0.107.79，mihomo DNS 上游接管到它，广告域名在解析层被拦。

## 一、DNS 链路图

```
mihomo (本机:1053, fake-ip)  ──上游──▶  AdGuard Home (127.0.0.1:53)  ──上游──▶  223.5.5.5 / 119.29.29.29
       │                                        │
       ▼                                        ▼
  手机/电视(走PAC或代理)               广告域名 → 0.0.0.0 (FilteredBlackList)
  国内域名 → GEOSITE,cn → 直连          正常域名 → 正常IP
```

- 覆盖面（当前阶段）：本机自身 + mihomo 分流链路上的域名解析。
- 手机侧：PAC 模式 DNS 在手机本地，AdGuard 拦不到；手机侧广告靠影视仓 parses/客户端方案（阶段二再推：手机 DNS 手动改 192.168.1.70 或路由器 DHCP 下发）。

## 二、端口与服务

| 项 | 值 |
|---|---|
| 服务 | systemd: AdGuardHome.service (enabled, active) |
| Web 管理台 | http://192.168.1.70:9092 (0.0.0.0) |
| DNS 监听 | 127.0.0.1:53 (阶段四验收后扩 0.0.0.0) |
| 管理员 | admin，密码在 /root/adguard-backup/adguard-credentials.txt |
| 安装目录 | /opt/AdGuardHome/ (二进制 + AdGuardHome.yaml + data/) |

## 三、过滤规则现状

| 名单 | 类型 | 条数 | 状态 |
|---|---|---|---|
| AdGuard DNS filter (filter_1) | 拦截 | 177,297 | 启用 |
| CHN: anti-AD (filter_21) | 拦截 | 98,823 | 启用 |
| BlueSkyXN ok.txt | 白名单兜底 | 216 | 启用 |

上游 DNS：223.5.5.5 / 119.29.29.29（与 mihomo 原配置等价，bootstrap 同款）

## 四、mihomo 侧改动（dns: 块，仅 2 行）

```yaml
# 改前
  nameserver: [223.5.5.5, 119.29.29.29]
# 改后
  nameserver: [127.0.0.1, "127.0.0.1:53"]  # WO-1001: DNS上游接管到 AdGuard Home:53
```

- default-nameserver 保持 223.5.5.5/119.29.29.29（bootstrap 防死锁，此时 127.0.0.1 还没起）
- nameserver-policy 全部保留原 IP（AdGuard 上游同款，语义等价，最小改动）
- 基线：改前 b34a7f9（config sha256 前缀 e16ec4349d6c800a）→ 改后 661a31a455bb4568
- 热加载：curl -X PUT http://127.0.0.1:9090/configs -d "{\"path\":\"/home/linxuan/mihomo-next/config.yaml\"}"

## 五、误伤三步自救

### 第1步：暂停保护（最快，10秒）
AdGuard 后台 → 顶部「暂停保护」按钮 → 选 30 秒/5 分钟 → 领完奖励自动恢复。不用改配置。

### 第2步：查日志加白名单（精准，1分钟）
AdGuard 后台 → 查询日志 → 找到被拦域名（红色）→ 点「允许」→ 即时生效。
常见误杀特征：阿里系 CDN 域名含 ad 字样、统计域名混用。

### 第3步：一键回滚（终极，30秒）
```bash
cd /home/linxuan/mihomo-next && ./rollback-dns.sh
```
脚本做的事：mihomo -t 预检 → nameserver 改回 223.5.5.5/119.29.29.29 → 热加载 → probe 自检。
已演练通过（回滚→恢复→再切回 AdGuard 双向可逆）。

## 六、看广告领奖励操作卡

1. 打开 AdGuard 后台（192.168.1.70:9092）
2. 点「暂停保护」选 1 分钟
3. 去看广告领奖励
4. 回来自动恢复（或者手动点恢复）

## 七、验收记录（2026-10-01）

- [x] doubleclick.net @127.0.0.1 → 0.0.0.0（拦截）
- [x] qq.com @127.0.0.1 → 157.255.219.143（放行）
- [x] mihomo probe 6/6 全绿（X 探针偶发超时为节点抖动，三种 DNS 态下均出现，直测 200 非本改动引入）
- [x] AdGuard stats: num_dns_queries=15, num_blocked_filtering=3（mihomo 流量确认进入）
- [x] querylog: upstream=223.5.5.5:53 / 119.29.29.29:53, reason=FilteredBlackList 拦截生效
- [x] 回滚脚本演练双向可逆
- [x] mihomo runtime 93 条规则数不降

## 八、Homarr 卡片（阶段三施工中）

- 卡片：AdGuard Home, href=http://home.nanshark.ccwu.cc:9092/, ping_url=http://home.nanshark.ccwu.cc:9092/login
- 探针已启用（pingEnabled:true），免密可开（公共面板）
