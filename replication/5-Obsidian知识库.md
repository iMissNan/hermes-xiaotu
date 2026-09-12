# 5-Obsidian知识库

> 一句话：系统的"记忆外置器官"——知识库（PARA 结构 + Git 时光机）加浏览器可访问的 Web 版。

## 1. 是什么

两件事合体：**知识库本体**是 Git 仓库（本仓即它的公开发布形态），双链笔记+时光机回滚；**obsidian-web** 让浏览器/平板直接读写库（配合 Homarr 卡片入口）。

## 2. 上游原址

- Obsidian：https://obsidian.md （桌面版按需安装）
- obsidian-web 镜像：`lscr.io/linuxserver/obsidian`（本机用 `linuxserver/obsidian:latest`）

## 3. 部署

```bash
# 数据目录
mkdir -p ~/.local/opt/obsidian-web/config
git clone <本仓地址> ~/data/obsidian-vault   # 知识库本体（复刻者也可以全新 init）

docker run -d --name obsidian-web \
  --restart unless-stopped \
  -p 8083:3000 -p 8084:3001 \
  -e TZ=Asia/Shanghai -e PUID=1000 -e PGID=1000 \
  -v ~/.local/opt/obsidian-web/config:/config \
  -v ~/data/obsidian-vault:/vaults/obsidian-vault \
  lscr.io/linuxserver/obsidian:latest
```

| 参数 | 说明 |
|---|---|
| `-p 8083` | Web 界面（kclienting 前端） |
| `-p 8084` | HTTPS 页面端口 |
| `/config` | 浏览器端 Obsidian 配置（持久化） |
| `/vaults/...` | **直接挂载 Git 仓库**——Web 端编辑即仓库文件 |

## 4. 配置

- 仓库治理规范（生命周期/防大文件/双层结构）见 `03-Areas/Obsidian知识库-5W1H自动化治理规范`；
- Git 自动提交可用 crontab 定时 `git add -A && git commit` + pushall 双推（本机由维护者手工/agent 操作为主）；
- 首次打开 Web 界面：选 vault → 指向 `/vaults/obsidian-vault`。

## 5. 数据重建

复刻者两种起法：clone 本仓（得到全部公开知识）或空库自建；`.obsidian/` 配置随仓走，Web 端个性化配置存 `~/.local/opt/obsidian-web/config` 自动生长。

## 6. 服务联动

- 被 6（Homarr 挂入口卡）、10（台账类笔记引用 Vaultwarden）；
- 本仓即复刻体系的家：`replication/` 全套指南就在库里。

## 7. 验证

```bash
docker ps | grep obsidian-web
curl -sI http://<内网IP>:8083 | head -1      # 门通
# 功能验证：Web 端新建一条笔记 → 服务器上 git -C ~/data/obsidian-vault status 能看到
```

## 8. 升级与回滚

```bash
docker pull lscr.io/linuxserver/obsidian:latest
docker rm -f obsidian-web    # 重跑第 3 节命令；config 卷与 vault 均持久化
```

知识库回滚靠 Git 本身（`git log`/`git checkout <commit>`），与容器版本无关。
