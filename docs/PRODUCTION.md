# 生产环境边界

- 项目：服务器监控看板
- 端口：5000
- 目录：/var/www/dashboard；采集器 /home/ubuntu/monitor/server_status.py
- 进程：nginx + cron

## 推荐检查

`python3 collector/server_status.py（会写状态，先在测试环境验证）`

## 不上传、不覆盖

status.json、.restart_state.json 和日志。这些内容只应通过独立的生产备份机制保存，不属于 Git 源码。

本仓库公开可见。任何真实凭据都不应写入代码、Issue、Actions 日志或 Git 历史。
