# 每日速读插件 daily60s

每日定时推送新闻速读、金价等内容到指定聊天流，同时支持关键词命令按需获取。

## 配置说明

编辑 `config.toml`：

- `fetch.timeout`：HTTP 请求超时秒数
- `fetch.sources`：数据源列表，每项包含：
  - `name`：数据源标识（英文）
  - `url`：API 接口地址
  - `keywords`：触发关键词列表，精确匹配（大小写不敏感）
  - `schedule_push`：是否纳入每日定时推送
- `schedule.push_time`：每日推送时间，格式 `HH:MM`
- `schedule.stream_ids`：推送目标 stream_id 列表
- `command.enabled`：是否允许关键词触发

## 数据源 API 格式

支持 JSON 和纯文本响应：
- JSON：优先读取 `news`、`content`、`data` 字段
- 纯文本：直接使用响应体
