# 服务器监控看板

技术栈：静态 HTML + Python 采集器 + cron。

## 维护

- 检查／构建：python3 collector/server_status.py（会写状态，先在测试环境验证）
- Agent 维护约束：见 `AGENTS.md`
- 生产目录、端口和数据边界：见 `docs/PRODUCTION.md`

本仓库只保存源码和文档，不保存生产密钥、用户数据或数据库。
