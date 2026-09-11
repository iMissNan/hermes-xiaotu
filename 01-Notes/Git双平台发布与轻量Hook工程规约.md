---
title: Git 双平台发布与轻量 Hook 工程规约
category: notes
status: active
updated: 2026-09-11
tags: [git, github, gitee, conventions, open-source]
---

# 🐙 Git 双平台发布与轻量 Hook 工程规约

> **摘要**：固化家庭服务器各公开开源项目及自研工具的 Git 版本管理体系，明确 GitHub 主仓 + Gitee 镜像双推策略、纯中文提交规范与 Agent 代劳边界。

---

## 1. 账号与平台映射基准

- **GitHub 主仓**：用户名 `iMissNan`（面向全球开源社区）；
- **Gitee 镜像仓**：用户名 `miss--you`（面向国内极速访问与镜像）；
- **只读源仓 vs 工作仓**：
  - `wiki`：维护者只读官方源仓；
  - `wiki-xiaotu`：Agent 协作工作仓。
- **凭据取用路径**：严禁硬编码明文密码，优先从本地 `state.db` 或 Vaultwarden 台账取用。

---

## 2. 提交规范与代理操作红线

### (1) ⛔ Agent 代劳红线
- **绝对铁律**：Agent 在执行 `git commit`、`git push`、打 Tag 或提交 Pull Request 之前，**必须先明确向维护者汇报并征得允许**，严禁擅自向远程推送代码！

### (2) 纯中文提交规范 (Conventional Commits 深度适配)
```text
<类型>(<作用域>): <简明中文说明>

[可选正文：详细说明变更背景、根因与测试验证命令]
```
- **常用类型**：
  - `feat`: 新增功能/特性；
  - `fix`: 缺陷修复；
  - `chore`: 依赖更新、生命周期管理、日常维护；
  - `docs`: 文档/知识库更新；
  - `refactor`: 重构（既不修复 bug 也不增加新功能）。

### (3) 轻量级 Shell Hook
- 拒绝重型 Node/Husky 依赖链，采用无依赖的纯 Bash 钩子进行本地防失控校验（如检查是否误提超过 10MB 的大二进制媒体）。

---

## 3. 极简运维与同步命令

```bash
# 检查当前仓库的远程双推配置
git remote -v

# 本地快速双推（需先走代理 7894 出口以防 reset）
git push origin master
git push gitee master
```

---

## 🔗 关联索引
- 上级主索引：[[Home|知识库主索引]]
- 凭据台账：[[03-Areas/账号与服务密码管理基线|账号与服务密码管理基线]]
- 网络代理支持：[[01-Notes/AI出口网络代理与Sing-box分流策略|AI 出口网络代理与 Sing-box 分流策略]]
