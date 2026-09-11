# 贡献指南

感谢你愿意为本项目贡献代码！在提交之前，请花 2 分钟阅读以下规范。

## 提交信息规范（Conventional Commits 中文版）

所有 commit message 必须遵循以下格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### type（必填，英文）

| type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(auth): 添加手机号一键登录` |
| `fix` | 修复缺陷 | `fix(parser): 修复中文乱码问题` |
| `docs` | 文档变更 | `docs(readme): 补充快速开始示例` |
| `style` | 代码格式 | `style(core): 统一缩进为 4 空格` |
| `refactor` | 重构 | `refactor(api): 拆分 gateway 为独立模块` |
| `perf` | 性能优化 | `perf(db): 优化批量查询为单条 SQL` |
| `test` | 测试相关 | `test(auth): 补充登录接口测试` |
| `chore` | 构建/依赖 | `chore(deps): 升级 requests 到 2.32` |
| `ci` | CI 配置 | `ci(github): 新增 release 自动构建` |
| `revert` | 回滚 | `revert: 回滚 v1.2.0 的登录重构` |

### scope（选填）

写影响模块名，如 `auth`、`db`、`core`。多模块用 `/` 分隔。

### subject（必填，核心）

- 用**动宾短语**：「添加 xxx」「修复 xxx」「优化 xxx」
- **不超过 50 个字符**（中文约 25 字）
- 结尾**不加句号**
- 禁止「修了个bug」「更新代码」这类空话

### body（选填但推荐）

说明**为什么改**（背景）、**怎么改**（方案）、**影响范围**。每行 ≤ 72 字符，与 header 之间空一行。

### footer（选填）

- 关联 issue：`Closes #12`（GitHub）/ `Closes #I5ABC1`（Gitee）
- 破坏性变更：`BREAKING CHANGE: 描述`

### 完整示例

```
feat(auth): 添加手机号一键登录功能

接入运营商一键登录 SDK，支持移动/联通/电信三网。
登录失败自动降级到短信验证码。

Closes #12
```

```
fix(parser): 修复中文文件名乱码问题

Windows 下上传的中文文件名按 GBK 解析导致乱码，
改为优先按 UTF-8 解码，失败时回退 GBK。

Closes #15
```

### 规范强制

仓库已配置 `scripts/commit-msg.sh` 钩子，格式不符的提交会被**直接拦截**。

## 开发流程

1. Fork 本仓库并 clone 到本地
2. 创建功能分支：`git checkout -b feat/你的功能名`
3. 开发并本地测试
4. 提交（遵循上述规范）
5. 推送并创建 Pull Request
6. 等待 review 与合并

## Issue 规范

- **Bug 报告**：使用 Bug 模板，写明复现步骤、期望行为、实际行为、环境信息
- **功能建议**：使用 Feature 模板，说明使用场景和期望效果
- 提交前先搜索是否已有相同 issue

## 代码风格

- 遵循项目已有的代码风格
- 提交前运行现有测试，确保不破坏已有功能

## 许可证

提交代码即表示你同意你的贡献以 [MIT](LICENSE) 许可证发布。
