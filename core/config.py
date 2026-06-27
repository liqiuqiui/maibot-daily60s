"""每日信息速递插件配置模型"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, cast

import re

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator

CONFIG_VERSION = "1.0.0"

ApiName = Literal["daily_news", "gold_price", "gas_price", "ai_news", "today_in_history", "it_news"]
PushType = Literal["text", "image"]
TargetFilterType = Literal["whitelist", "blacklist"]

VALID_API_NAMES: tuple[ApiName, ...] = (
    "daily_news",
    "gold_price",
    "gas_price",
    "ai_news",
    "today_in_history",
    "it_news",
)
_PUSH_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _normalize_string(value: Any) -> str:
    """规范化字符串配置值"""
    return "" if value is None else str(value).strip()


def _normalize_positive_int(value: Any, default: int) -> int:
    """规范化正整数配置值"""
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            parsed_value = int(normalized_value)
            if parsed_value > 0:
                return parsed_value
    return default


def _normalize_string_list(value: Any) -> list[str]:
    """规范化字符串列表配置值，去除空白与重复项"""
    if not isinstance(value, list):
        return []

    normalized_values: list[str] = []
    seen_values: set[str] = set()
    for item in value:
        item_text = _normalize_string(item)
        if not item_text or item_text in seen_values:
            continue
        seen_values.add(item_text)
        normalized_values.append(item_text)
    return normalized_values


def _normalize_api_names(value: Any, field_name: str) -> list[ApiName]:
    """规范化 API key 列表，过滤空值与重复项，并校验 API key"""
    raw_values = _normalize_string_list(value)
    if not raw_values:
        raise ValueError(f"{field_name} 不能为空")

    invalid_values = [item for item in raw_values if item not in VALID_API_NAMES]
    if invalid_values:
        valid_values = ", ".join(VALID_API_NAMES)
        raise ValueError(f"{field_name} 包含未知 API：{', '.join(invalid_values)}可用值：{valid_values}")

    return cast(list[ApiName], raw_values)


def _normalize_keyword_list(value: Any, field_name: str) -> list[str]:
    """规范化命令关键词或别名列表，所有项必须以 / 开头"""
    keywords = _normalize_string_list(value)
    invalid_keywords = [keyword for keyword in keywords if not keyword.startswith("/")]
    if invalid_keywords:
        raise ValueError(f"{field_name} 必须以 / 开头：{', '.join(invalid_keywords)}")
    return keywords


def _normalize_push_type(value: Any, field_name: str) -> PushType:
    """规范化推送内容类型"""
    normalized_value = _normalize_string(value).lower()
    if normalized_value not in ("text", "image"):
        raise ValueError(f"{field_name} 必须是 text 或 image")
    return cast(PushType, normalized_value)


def _normalize_push_time_value(value: Any) -> str:
    """规范化推送时间字段"""
    normalized_value = _normalize_string(value) or "08:00"
    if not _PUSH_TIME_RE.fullmatch(normalized_value):
        raise ValueError("push_time 必须是 HH:MM 格式，例如 08:00")

    hour, minute = normalized_value.split(":", maxsplit=1)
    if int(hour) > 23 or int(minute) > 59:
        raise ValueError("push_time 必须是有效时间，例如 08:00")
    return normalized_value


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置"""

    __ui_label__: ClassVar[str] = "插件设置"
    __ui_icon__: ClassVar[str] = "package"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=True,
        description="是否启用插件",
        json_schema_extra={
            "hint": "关闭后插件不响应任何消息，也不执行定时推送",
            "label": "启用插件",
            "order": 0,
        },
    )
    config_version: str = Field(
        default=CONFIG_VERSION,
        description="当前配置结构版本",
        json_schema_extra={"disabled": True, "label": "配置版本", "order": 99},
    )


class FetchConfig(PluginConfigBase):
    """数据源拉取配置"""

    __ui_label__: ClassVar[str] = "数据源"
    __ui_icon__: ClassVar[str] = "globe"
    __ui_order__: ClassVar[int] = 1

    base_urls: list[str] = Field(
        default_factory=lambda: ["https://60s.viki.moe"],
        description="API 根地址列表，按顺序尝试，前一个失败时自动切换到下一个",
        json_schema_extra={
            "hint": "填写多个地址可实现冗余回退，例如自建api与官方api并列",
            "label": "数据源地址列表",
            "placeholder": "请填写完整的api地址",
        },
    )
    timeout: int = Field(
        default=10,
        description="HTTP 请求超时秒数",
        json_schema_extra={
            "hint": "超过该时长未收到响应时视为请求失败，自动切换下一个api地址",
            "label": "超时秒数",
        },
    )

    @field_validator("timeout", mode="before")
    @classmethod
    def _normalize_timeout(cls, value: Any) -> int:
        return _normalize_positive_int(value, 10)

    @field_validator("base_urls", mode="before")
    @classmethod
    def _normalize_base_urls(cls, value: Any) -> list[str]:
        base_urls = _normalize_string_list(value)
        if not base_urls:
            raise ValueError("fetch.base_urls 不能为空")
        return base_urls


class ScheduleConfig(PluginConfigBase):
    """定时推送任务配置"""

    enabled: bool = Field(
        default=True,
        description="是否启用该定时推送任务",
        json_schema_extra={"label": "启用任务"},
    )
    apis: list[ApiName] = Field(
        default_factory=list,
        description="该任务要推送的内容类型",
        json_schema_extra={"label": "推送内容", "hint": "可选择一个或多个内容类型"},
    )
    groups_type: TargetFilterType = Field(
        default="whitelist",
        description="群聊名单模式",
        json_schema_extra={"label": "群聊名单模式", "hint": "whitelist 仅推送名单内群聊，blacklist 跳过名单内群聊"},
    )
    groups: list[str] = Field(
        default_factory=list,
        description="群聊名单",
        json_schema_extra={"label": "群聊名单", "hint": "填写群号；留空时由名单模式决定是否限制"},
    )
    users_type: TargetFilterType = Field(
        default="whitelist",
        description="私聊名单模式",
        json_schema_extra={"label": "私聊名单模式", "hint": "whitelist 仅推送名单内私聊，blacklist 跳过名单内私聊"},
    )
    users: list[str] = Field(
        default_factory=list,
        description="私聊名单",
        json_schema_extra={"label": "私聊名单", "hint": "填写用户 ID；留空时由名单模式决定是否限制"},
    )
    push_type: PushType = Field(
        default="image",
        description="推送消息格式",
        json_schema_extra={"label": "推送消息格式", "hint": "text 为文本，image 为图片"},
    )
    push_time: str = Field(
        default="08:00",
        description="每日推送时间，格式：HH:MM",
        json_schema_extra={"label": "推送时间", "hint": "24 小时制，例如 08:00 或 20:30"},
    )

    @field_validator("apis", mode="before")
    @classmethod
    def _normalize_apis(cls, value: Any) -> list[ApiName]:
        return _normalize_api_names(value, "schedule_push_config.schedule_list.apis")

    @field_validator("groups", mode="before")
    @classmethod
    def _normalize_groups(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("users", mode="before")
    @classmethod
    def _normalize_users(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("push_time", mode="before")
    @classmethod
    def _normalize_push_time(cls, value: Any) -> str:
        return _normalize_push_time_value(value)

    @field_validator("push_type", mode="before")
    @classmethod
    def _normalize_push_type(cls, value: Any) -> PushType:
        return _normalize_push_type(value, "schedule_push_config.schedule_list.push_type")


class TriggerConfig(PluginConfigBase):
    """命令触发规则配置"""

    enabled: bool = Field(
        default=True,
        description="是否启用该命令触发规则",
        json_schema_extra={"label": "启用规则"},
    )
    apis: list[ApiName] = Field(
        default_factory=list,
        description="该规则允许触发的内容类型",
        json_schema_extra={"label": "触发内容", "hint": "可选择一个或多个内容类型"},
    )
    groups_type: TargetFilterType = Field(
        default="whitelist",
        description="群聊名单模式",
        json_schema_extra={
            "label": "群聊名单模式",
            "hint": "whitelist 仅允许名单内群聊触发，blacklist 禁止名单内群聊触发",
        },
    )
    groups: list[str] = Field(
        default_factory=list,
        description="群聊名单",
        json_schema_extra={"label": "群聊名单", "hint": "填写群号；留空时由名单模式决定是否限制"},
    )
    users_type: TargetFilterType = Field(
        default="whitelist",
        description="私聊名单模式",
        json_schema_extra={
            "label": "私聊名单模式",
            "hint": "whitelist 仅允许名单内私聊触发，blacklist 禁止名单内私聊触发",
        },
    )
    users: list[str] = Field(
        default_factory=list,
        description="私聊名单",
        json_schema_extra={"label": "私聊名单", "hint": "填写用户 ID；留空时由名单模式决定是否限制"},
    )
    push_type: PushType = Field(
        default="image",
        description="回复消息格式",
        json_schema_extra={"label": "回复消息格式", "hint": "text 为文本，image 为图片"},
    )

    @field_validator("apis", mode="before")
    @classmethod
    def _normalize_apis(cls, value: Any) -> list[ApiName]:
        return _normalize_api_names(value, "command_trigger_config.trigger_list.apis")

    @field_validator("groups", mode="before")
    @classmethod
    def _normalize_groups(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("users", mode="before")
    @classmethod
    def _normalize_users(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("push_type", mode="before")
    @classmethod
    def _normalize_push_type(cls, value: Any) -> PushType:
        return _normalize_push_type(value, "command_trigger_config.trigger_list.push_type")


class SchedulePush(PluginConfigBase):
    """定时推送配置"""

    __ui_label__: ClassVar[str] = "定时推送"
    __ui_icon__: ClassVar[str] = "clock"
    __ui_order__: ClassVar[int] = 2

    schedule_list: list[ScheduleConfig] = Field(
        default_factory=list,
        json_schema_extra={"label": "定时推送任务"},
    )


class CommandTrigger(PluginConfigBase):
    """命令触发配置"""

    __ui_label__: ClassVar[str] = "命令触发"
    __ui_icon__: ClassVar[str] = "message-square"
    __ui_order__: ClassVar[int] = 3

    trigger_list: list[TriggerConfig] = Field(
        default_factory=lambda: [
            TriggerConfig(apis=["ai_news", "daily_news", "gas_price", "gold_price", "it_news", "today_in_history"])
        ],
        json_schema_extra={"label": "命令触发规则"},
    )


class CommandAlias(PluginConfigBase):
    """为触发命令配置别名"""

    __ui_label__: ClassVar[str] = "命令别名配置"
    __ui_icon__: ClassVar[str] = "terminal"
    __ui_order__: ClassVar[int] = 4

    daily_news: list[str] = Field(
        default_factory=list,
        json_schema_extra={"label": "每日新闻(daily_news)", "hint": "默认 /daily_news"},
    )
    gold_price: list[str] = Field(
        default_factory=list, json_schema_extra={"label": "金价(gold_price)", "hint": "默认 /gold_price"}
    )
    gas_price: list[str] = Field(
        default_factory=list, json_schema_extra={"label": "油价(gas_price)", "hint": "默认 /gas_price"}
    )
    ai_news: list[str] = Field(
        default_factory=list, json_schema_extra={"label": "AI 新闻(ai_news)", "hint": "默认 /ai_news"}
    )
    today_in_history: list[str] = Field(
        default_factory=list,
        json_schema_extra={"label": "历史上的今天(today_in_history)", "hint": "默认 /today_in_history"},
    )
    it_news: list[str] = Field(
        default_factory=list, json_schema_extra={"label": "IT 新闻(it_news)", "hint": "默认 /it_news"}
    )

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_aliases(cls, value: Any) -> list[str]:
        return _normalize_keyword_list(value, "command_alias_config")


class Daily60sPluginConfig(PluginConfigBase):
    """每日信息速递插件完整配置"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    schedule_push_config: SchedulePush = Field(default_factory=SchedulePush)
    command_trigger_config: CommandTrigger = Field(default_factory=CommandTrigger)
    command_alias_config: CommandAlias = Field(default_factory=CommandAlias)
