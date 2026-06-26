# 每日信息速递 daily60s

每日定时推送新闻速递、金价等内容到指定 QQ 群组，同时支持关键词命令按需获取。

## 命令说明

- `/menu`、`/help`、`/菜单`、`/帮助`：查看每日信息速递菜单
- `/60s`、`/daily60s`：获取每日 60 秒新闻
- `/gold_price`：获取黄金价格
- `/gas_price <地区>`、`/gas <地区>`：获取指定地区油价
- `/ai_news [YYYY-MM-DD] [all]`、`/ai [YYYY-MM-DD] [all]`：获取 AI 资讯快报
- `/today_history [YYYY-MM-DD]`、`/history_today [YYYY-MM-DD]`：获取历史上的今天
- `/it_news [limit]`、`/it [limit]`：获取实时 IT 资讯

## 配置说明

编辑 `config.toml`：

- `plugin.enabled`：是否启用插件
- `fetch.timeout`：HTTP 请求超时秒数
- `fetch.base_urls`：数据源地址列表，按顺序尝试，前一个失败自动切换下一个

每个 API 独立配置（`daily_news` / `gold_price` / `gas_price`）：

- `enabled`：是否启用此 API
- `keywords`：触发关键词列表，必须以 / 开头，精确匹配（大小写不敏感）
- `schedule_push`：是否启用每日定时推送
- `push_time`：每日推送时间，格式 `HH:MM`（24 小时制）
- `push_groups`：推送目标 QQ 群号列表，推送时自动解析群号对应的聊天流
- `push_format`（仅 daily_news）：推送格式，`text`（文字新闻列表）或 `image`（封面图片）

## 数据源 API 格式

支持 JSON 和纯文本响应：
- JSON：优先读取 `news`、`content`、`data` 字段
- 纯文本：直接使用响应体
