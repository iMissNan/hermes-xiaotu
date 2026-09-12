# 变更日志

本项目所有重要变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增
- AO 多智能体工作流系统主卡（引擎/大盘/汇报面板/补丁台账/历史教训）
- 多智能体工作流设计规格笔记（验收五断言/模型分级/择路规则/防劫持）
- TokenHub 主卡补记 v3 流水线实施链路与资产现状

### 变更
- 主索引 Home.md 接入 AO 流水线入口
- 全库真实环境值（域名/IP/口令/账号）脱敏为 `<占位符>`，真实值仅存本地不入库
- 仓库级双钩子入库（commit-msg 格式校验 + pre-push 敏感真值扫描），clone 即可启用
- Git 规约卡账号事实修正（GitHub=iMissNan）并更新双推命令为 pushall
- 10Router 主卡补齐从零复刻部署指南（上游原址/Docker 命令/CN 网络增强补丁/升级迁移），补丁随仓发布
- 新增系统级复刻体系 replication/：DEPLOYMENT 路线图 + 13 份组件指南 + 验收清单；monpanel/MarsTV/YPM补丁/AO交接面板源码入仓 assets/；服务卡双链回写
- 公开仓库骨架：README/许可证/协作文档/平台模板（conventional-commits 双钩子）

### 移除
- （移除的功能写这里）

---

## [0.1.0] - 2026-08-01

### 新增
- 知识库体系初始化（PARA 目录/生命周期管家/Git 时光机）

[未发布]: https://github.com/iMissNan/hermes-xiaotu/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/iMissNan/hermes-xiaotu/releases/tag/v0.1.0
