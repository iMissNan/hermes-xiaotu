# 10-Vaultwarden台账

> 一句话：全家的密码保险柜——轻量 Bitwarden 服务端，所有服务口令/凭据的统一台账（内网 + HTTPS 入口）。

## 1. 是什么

Vaultwarden 是 Rust 实现的 Bitwarden 兼容服务端。本系统用它做**凭据单一事实源**：所有自托管服务的登录口令、API 凭据登记在册，浏览器装 Bitwarden 插件直连内网地址自动填充。

## 2. 上游原址

- 项目：https://github.com/dani-garcia/vaultwarden （AGPL-3.0，活跃）
- 镜像：`vaultwarden/server:latest`
- HTTPS 门面：nginx 容器（vault-tls，同源证书）

## 3. 部署

### 3.1 主服务

```bash
sudo mkdir -p /opt/vaultwarden/data

docker run -d --name vaultwarden \
  --restart unless-stopped \
  -p 20130:80 \
  -v /opt/vaultwarden/data:/data \
  -e DOMAIN="https://<你的域名>:8445" \
  -e SIGNUPS_ALLOWED=false \
  vaultwarden/server:latest
```

| 参数 | 说明 |
|---|---|
| `DOMAIN` | 必须与最终访问 URL 一致（WebCrypto 要求），否则登录页报错 |
| `SIGNUPS_ALLOWED=false` | 关注册（建完自己的账号后防陌生人）——首启可先 true，建号后改 false 重建 |

### 3.2 HTTPS 门面（vault-tls，nginx 容器）

```bash
# 证书：acme.sh 签发 <你的域名>（ecc），落到 ~/.acme.sh/<你的域名>_ecc/
mkdir -p ~/.local/share/vault-tls
cat > ~/.local/share/vault-tls/nginx-le.conf <<'EOF'
server {
    listen 8445 ssl;
    ssl_certificate     /etc/nginx/tls/fullchain.cer;
    ssl_certificate_key /etc/nginx/tls/<你的域名>.key;
    location / { proxy_pass http://<内网IP>:20130; }
}
EOF

docker run -d --name vault-tls \
  --restart unless-stopped \
  -p 8445:8445 \
  -v ~/.local/share/vault-tls/nginx-le.conf:/etc/nginx/conf.d/default.conf:ro \
  -v ~/.acme.sh/<你的域名>_ecc:/etc/nginx/tls:ro \
  nginx:alpine
```

## 4. 配置

- 管理面板（`/admin`）token：环境变量 `ADMIN_TOKEN` 加上后可网页调参；
- 浏览器/手机端 Bitwarden 客户端：自托管服务器 URL 填 `https://<你的域名>:8445`。

## 5. 数据重建

- 新库逐条录入各服务口令（或从密码管理器导入 CSV）；
- 数据全在 `/opt/vaultwarden/data`（SQLite），备份=停容器拷目录；
- **口令是复刻者自己的**——本仓文档中所有 `<统一口令>` 类占位符的真值都应录进这里。

## 6. 服务联动

- 被依赖：全体（人查口令的唯一入口）；
- 与 5（知识库）：服务卡的口令字段一律写"见台账"不写真值。

## 7. 验证

```bash
docker ps | grep -E 'vaultwarden|vault-tls'
curl -skI https://<你的域名>:8445 | head -1     # HTTPS 门通
# 功能验证：注册/登录自己账号 → 建一条测试条目 → 浏览器插件自动填充成功
```

## 8. 升级与回滚

```bash
docker pull vaultwarden/server:latest
docker rm -f vaultwarden   # 重跑第 3.1 节；data 卷不动即数据无损
```

- 证书续期：acme.sh 的 cron 自动续，续完 `docker restart vault-tls`（可挂 cron）；
- 数据库损坏回滚：还原备份目录。
