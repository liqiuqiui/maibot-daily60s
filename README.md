# 每日信息速递 daily60s

每日信息速递插件，用于在 MaiBot 中按需查询或定时推送 60s API 的新闻、金价、油价、AI 资讯、历史事件和 IT 资讯。

插件支持群聊和私聊，支持文本与图片两种回复格式，并可通过配置控制命令触发范围、命令别名、推送目标和推送时间。

## 功能特性

- 按命令查询每日新闻、黄金价格、今日油价、AI 资讯快报、历史上的今天、实时 IT 资讯。
- 按配置每日定时推送一个或多个内容类型。
- 支持群聊和私聊名单控制，名单模式可选 `whitelist` 或 `blacklist`。
- 支持文本消息和图片消息；图片模式会使用 MaiBot 的 `render.html2png` 能力渲染部分内容。
- 支持多个 API 根地址，前一个数据源失败时自动尝试下一个。
- 支持配置命令别名，例如把 `/daily_news` 额外配置为 `/60s`。

## 支持内容

| API 名称 | 默认命令 | 说明 | 参数 |
| --- | --- | --- | --- |
| `daily_news` | `/daily_news` | 每日 60 秒新闻简报 | 不接受参数 |
| `gold_price` | `/gold_price` | 最新黄金价格行情 | 不接受参数 |
| `gas_price` | `/gas_price <地区>` | 指定地区今日油价 | 必填地区，例如 `北京` |
| `ai_news` | `/ai_news [YYYY-MM-DD] [all]` | AI 行业资讯快报 | 可选日期；可选 `all` |
| `today_in_history` | `/today_in_history [YYYY-MM-DD]` | 历史上的今天 | 可选日期 |
| `it_news` | `/it_news [limit]` | 实时 IT 资讯 | 可选条数，范围 1 到 50 |

## 命令说明

- `/menu`、`/help`、`/菜单`、`/帮助`：查看每日信息速递菜单
- `/daily_news`：获取每日 60 秒新闻
- `/gold_price`：获取黄金价格
- `/gas_price <地区>`：获取指定地区油价
- `/ai_news [YYYY-MM-DD] [all]`：获取 AI 资讯快报
- `/today_in_history [YYYY-MM-DD]`：获取历史上的今天
- `/it_news [limit]`：获取实时 IT 资讯

命令参数不符合要求时，插件会回复对应命令的用法提示。命令别名需要在 `command_alias_config` 中配置，必须以 `/` 开头。

## 配置说明

编辑 `config.toml`：

- `plugin.enabled`：是否启用插件
- `fetch.timeout`：HTTP 请求超时秒数
- `fetch.base_urls`：数据源地址列表，按顺序尝试，前一个失败自动切换下一个

可用 API 名称：

- `daily_news`
- `gold_price`
- `gas_price`
- `ai_news`
- `today_in_history`
- `it_news`

命令触发配置：

- `command_trigger_config.trigger_list`：命令触发规则列表
- `trigger_list.enabled`：是否启用该触发规则
- `trigger_list.apis`：该规则允许触发的 API 列表
- `trigger_list.groups_type` / `trigger_list.groups`：群聊白名单或黑名单；名单为空时允许全部群聊触发
- `trigger_list.users_type` / `trigger_list.users`：私聊白名单或黑名单；名单为空时允许全部私聊触发
- `trigger_list.push_type`：命令回复格式，`text` 或 `image`
- `command_alias_config.<api_name>`：为指定 API 追加命令别名，必须以 `/` 开头

定时推送配置：

- `schedule_push_config.schedule_list`：定时推送任务列表
- `schedule_list.enabled`：是否启用该定时任务
- `schedule_list.apis`：该任务要推送的 API 列表
- `schedule_list.push_time`：每日推送时间，格式 `HH:MM`（24 小时制）
- `schedule_list.groups_type` / `schedule_list.groups`：群聊白名单或黑名单
- `schedule_list.users_type` / `schedule_list.users`：私聊白名单或黑名单
- `schedule_list.push_type`：定时推送格式，`text` 或 `image`

定时推送名单行为：

- `whitelist`：只推送显式配置的目标；列表为空时没有该类型推送目标。
- `blacklist`：推送 MaiBot 已存在聊天流中未被排除的目标；列表为空时表示推送全部已存在聊天流。
- 群聊目标填写 QQ 群号，私聊目标填写用户 ID。
- 默认 `schedule_list = []`，不会执行任何定时推送；需要添加任务后才会启动实际推送。

## 配置示例

### 添加命令别名

```toml
[command_alias_config]
daily_news = ["/60s", "/daily60s"]
gold_price = ["/gold"]
gas_price = ["/gas"]
ai_news = ["/ai"]
today_in_history = ["/history_today"]
it_news = ["/it"]
```

### 只允许指定群聊触发图片回复

```toml
[[command_trigger_config.trigger_list]]
enabled = true
apis = ["daily_news", "ai_news", "it_news"]
groups_type = "whitelist"
groups = ["123456789"]
users_type = "whitelist"
users = []
push_type = "image"
```

### 每天 08:00 向指定群推送新闻和金价

```toml
[[schedule_push_config.schedule_list]]
enabled = true
apis = ["daily_news", "gold_price"]
groups_type = "whitelist"
groups = ["123456789"]
users_type = "whitelist"
users = []
push_type = "image"
push_time = "08:00"
```

### 每天 20:30 推送 AI 与 IT 资讯到所有已存在群聊，排除一个群

```toml
[[schedule_push_config.schedule_list]]
enabled = true
apis = ["ai_news", "it_news"]
groups_type = "blacklist"
groups = ["987654321"]
users_type = "whitelist"
users = []
push_type = "text"
push_time = "20:30"
```

## 数据源说明

默认数据源为：

```toml
[fetch]
base_urls = ["https://60s.viki.moe"]
timeout = 10
```

插件会根据 API 名称访问固定路径：

- `daily_news`：`/v2/60s`
- `gold_price`：`/v2/gold-price`
- `gas_price`：`/v2/fuel-price`
- `ai_news`：`/v2/ai-news`
- `today_in_history`：`/v2/today-in-history`
- `it_news`：`/v2/it-news`

如果配置了多个 `base_urls`，插件会按顺序尝试；当前地址请求失败时会自动尝试下一个地址。

## 注意事项

- 图片回复依赖 MaiBot 的 `render.html2png` 能力；如果宿主环境不支持渲染，建议把 `push_type` 改为 `text`。
- `daily_news` 的图片模式优先使用数据源返回的图片地址；下载失败时会回退为文本。
- `gas_price` 必须提供地区参数，例如 `/gas_price 北京`。
- `it_news` 的 `limit` 必须是 1 到 50 之间的整数。
- `ai_news` 最多接受两个参数，支持日期和 `all`，例如 `/ai_news 2026-06-27` 或 `/ai_news all`。
- 定时推送以插件运行机器的本地时间判断；同一个任务当天成功投递至少一个目标后，不会重复推送。
