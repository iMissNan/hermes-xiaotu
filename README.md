# hermes-xiaotu · 小兔知识库

> 家庭服务器自动化运维的 Obsidian 知识库公开镜像 —— 由 Hermes Agent（AI 助手"小兔"）维护，本地 Git 时光机 + 生命周期管家双重治理，定期同步至此。

## 这是什么

一套围绕自托管 AI 基础设施的运维知识库，采用 PARA 体系组织：

| 目录 | 内容 |
|---|---|
| `01-Notes/` | 长青经验：多智能体工作流设计规格、排障 SOP、避坑指南 |
| `02-Projects/` | 服务主卡：AO 工作流引擎、AI 网关、代币管家、媒体中心等，一系统一卡 |
| `03-Areas/` | 长期基准：网络拓扑、密码与凭据管理基线 |
| `04-Archives/` | 已下线服务归档 |
| `00-Inbox/` | 临时碎片收件箱（自动生命周期淘汰） |

## 快速开始

```bash
git clone https://github.com/iMissNan/hermes-xiaotu.git
cd hermes-xiaotu

# 启用提交模板与仓库级钩子（提交格式校验 + 敏感真值扫描）
git config commit.template .gitmessage
git config core.hooksPath hooks
```

用 [Obsidian](https://obsidian.md) 打开本目录即可作为知识库使用；仓库内所有真实环境值（域名/IP/口令/账号）均以 `<占位符>` 书写，复刻时全局替换为你自己的环境值。

## 治理规则（写库纪律）

- **单例主卡**：每个运行中的服务只有一张定稿主卡，更新走"原位追加变更历史"，禁止碎片文件
- **双链织网**：所有卡片经 `Home.md` 主索引互联，零孤岛
- **Git 时光机**：本地仓每次治理自动提交，可秒级回退
- **冷热分级**：对话流水账留会话库、日常偏好留记忆引擎，只有终局知识入本库

## 声明

- 涉及真实环境（域名/IP/口令/账号）一律以 `<占位符>` 书写，真实值仅存本地（`.gitignore` 排除），**本库不含任何 API 密钥 / token**，推送前经双重敏感扫描（真值内容扫描 + 密钥形态扫描）。
- Commit 遵循 Conventional Commits（type 英文 + 中文描述），GitHub 主仓 + Gitee 镜像双平台同步。

## 许可证

[MIT](LICENSE)
