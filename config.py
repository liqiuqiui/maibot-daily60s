"""每日速读插件配置模型。"""

from __future__ import annotations

from typing import Any, ClassVar, List, Literal

import logging
import re

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator

from .fetcher import API_REGISTRY

LOGGER = logging.getLogger("daily60s.config")

_PUSH_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

SUPPORTED_CONFIG_VERSION = "1.4.0"


def _normalize_string(value: Any) -> str:
    """规范化字符串配置值。"""
    return "" if value is None else str(value).strip()


def _normalize_positive_int(value: Any, default: int) -> int:
    """规范化正整数配置值。"""
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            parsed_value = int(normalized_value)
            if parsed_value > 0:
                return parsed_value
    return default


def _normalize_string_list(value: Any) -> List[str]:
    """规范化字符串列表配置值，去除空白与重复项。"""
    if not isinstance(value, list):
        return []
    normalized_values: List[str] = []
    seen_values: set[str] = set()
    for item in value:
        item_text = _normalize_string(item)
        if not item_text or item_text in seen_values:
            continue
        seen_values.add(item_text)
        normalized_values.append(item_text)
    return normalized_values


def _normalize_push_time_value(value: Any) -> str:
    """规范化推送时间字段，格式非法时记录警告。"""
    normalized_value = _normalize_string(value)
    if normalized_value and not _PUSH_TIME_RE.match(normalized_value):
        LOGGER.warning(
            "push_time 格式非法：'%s'，应为 HH:MM 格式，该 API 定时推送将在启动时被禁用。",
            normalized_value,
        )
    return normalized_value or "08:00"


class ApiConfig(PluginConfigBase):
    """单个 API 的可配置部分基类。

    API 路径、请求参数和格式化器均由代码硬编码（见 fetcher.py API_REGISTRY），
    此处只保存用户可调整的字段。
    """

    name: str = Field(
        default="",
        description="API 标识，对应代码内 API_REGISTRY 的键，不可更改。",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    enabled: bool = Field(
        default=True,
        description="是否启用此 API（命令触发与定时推送均受此开关控制）。",
        json_schema_extra={"label": "启用", "order": 0},
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词列表，必须以 / 开头，消息第一个词与关键词精确匹配时触发。",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，例如 /60s。大小写不敏感。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/60s",
        },
    )
    schedule_push: bool = Field(
        default=False,
        description="是否启用每日定时推送。",
        json_schema_extra={"label": "定时推送", "order": 2},
    )
    push_time: str = Field(
        default="08:00",
        description="每日推送时间，HH:MM 格式（24 小时制）。",
        json_schema_extra={
            "hint": "格式必须为 HH:MM，例如 08:00 或 20:30。格式非法时定时推送将被禁用。",
            "label": "推送时间",
            "order": 3,
            "placeholder": "08:00",
        },
    )
    push_groups: List[str] = Field(
        default_factory=list,
        description="定时推送的目标 QQ 群号列表，支持多个群组。",
        json_schema_extra={
            "hint": "填写 QQ 号即可，例如 123456789。推送时会自动解析群号对应的聊天流。",
            "label": "推送目标群号",
            "order": 4,
            "placeholder": "例如：123456789",
        },
    )

    push_users: List[str] = Field(
        default_factory=list,
        description="定时推送的目标私聊 QQ 号列表。",
        json_schema_extra={
            "hint": "填写 QQ 号即可，例如 123456789。",
            "label": "推送目标私聊 QQ 号",
            "order": 5,
            "placeholder": "例如：123456789",
        },
    )

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        return _normalize_string(value)

    @field_validator("keywords", mode="before")
    @classmethod
    def _normalize_keywords(cls, value: Any) -> List[str]:
        """规范化关键词列表，过滤不以 / 开头的项。"""
        raw = _normalize_string_list(value)
        valid = [k for k in raw if k.startswith("/")]
        if len(valid) != len(raw):
            LOGGER.warning("部分关键词不以 / 开头，已自动过滤：%s", [k for k in raw if not k.startswith("/")])
        return valid

    @field_validator("push_groups", mode="before")
    @classmethod
    def _normalize_push_groups(cls, value: Any) -> List[str]:
        return _normalize_string_list(value)

    @field_validator("push_users", mode="before")
    @classmethod
    def _normalize_push_users(cls, value: Any) -> List[str]:
        return _normalize_string_list(value)

    @field_validator("push_time", mode="before")
    @classmethod
    def _normalize_push_time(cls, value: Any) -> str:
        return _normalize_push_time_value(value)


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__: ClassVar[str] = "插件设置"
    __ui_icon__: ClassVar[str] = "package"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=True,
        description="是否启用插件。",
        json_schema_extra={
            "hint": "关闭后插件不响应任何消息，也不执行定时推送。",
            "label": "启用插件",
            "order": 0,
        },
    )
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="当前配置结构版本。",
        json_schema_extra={"disabled": True, "hidden": True, "label": "配置版本", "order": 99},
    )

    @field_validator("config_version", mode="before")
    @classmethod
    def _normalize_config_version(cls, value: Any) -> str:
        normalized_value = _normalize_string(value)
        return normalized_value or SUPPORTED_CONFIG_VERSION


class MessageServerConfig(PluginConfigBase):
    """OneBot HTTP 消息服务器配置。"""

    __ui_label__: ClassVar[str] = "消息服务器"
    __ui_icon__: ClassVar[str] = "server"
    __ui_order__: ClassVar[int] = 1

    host: str = Field(
        default="http://127.0.0.1",
        description="OneBot HTTP 服务地址，含协议前缀，例如 http://127.0.0.1。",
        json_schema_extra={
            "hint": "必须包含协议前缀，如 http:// 或 https://。",
            "label": "服务地址",
            "order": 0,
            "placeholder": "http://127.0.0.1",
        },
    )
    port: int = Field(
        default=5700,
        description="OneBot HTTP 服务端口。",
        json_schema_extra={
            "label": "端口",
            "order": 1,
            "step": 1,
        },
    )
    token: str = Field(
        default="",
        description="access token，为空时不附加鉴权参数。",
        json_schema_extra={
            "hint": "对应 OneBot 配置中的 access_token，为空时不鉴权。",
            "label": "Token",
            "order": 2,
            "placeholder": "留空表示不鉴权",
        },
    )

    @field_validator("host", mode="before")
    @classmethod
    def _normalize_host(cls, value: Any) -> str:
        return _normalize_string(value) or "http://127.0.0.1"

    @field_validator("port", mode="before")
    @classmethod
    def _normalize_port(cls, value: Any) -> int:
        return _normalize_positive_int(value, 5700)

    @field_validator("token", mode="before")
    @classmethod
    def _normalize_token(cls, value: Any) -> str:
        return _normalize_string(value)


class FetchConfig(PluginConfigBase):
    """数据源拉取配置。"""

    __ui_label__: ClassVar[str] = "数据源"
    __ui_icon__: ClassVar[str] = "globe"
    __ui_order__: ClassVar[int] = 2

    base_urls: List[str] = Field(
        default_factory=lambda: ["https://60s.viki.moe"],
        description="API 根地址列表，按顺序尝试，前一个失败时自动切换到下一个。",
        json_schema_extra={
            "hint": "填写多个地址可实现冗余回退，例如自建实例与官方实例并列。",
            "label": "数据源地址列表",
            "order": 9,
            "placeholder": "https://60s.viki.moe",
        },
    )

    timeout: int = Field(
        default=10,
        description="HTTP 请求超时秒数。",
        json_schema_extra={
            "hint": "超过该时长未收到响应时视为请求失败，自动切换下一个 base_url。",
            "label": "超时秒数",
            "order": 1,
            "step": 1,
        },
    )

    @field_validator("timeout", mode="before")
    @classmethod
    def _normalize_timeout(cls, value: Any) -> int:
        return _normalize_positive_int(value, 10)

    @field_validator("base_urls", mode="before")
    @classmethod
    def _normalize_base_urls(cls, value: Any) -> List[str]:
        return _normalize_string_list(value)


class DailyNewsApiConfig(ApiConfig):
    """每日60秒 API 配置（路径：/v2/60s，无参数）。"""

    __ui_label__: ClassVar[str] = "每日60秒"
    __ui_icon__: ClassVar[str] = "newspaper"
    __ui_order__: ClassVar[int] = 3

    name: str = Field(
        default="daily_news",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/60s", "/daily60s"],
        description="触发关键词列表，必须以 / 开头。",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，大小写不敏感。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/60s",
        },
    )
    schedule_push: bool = Field(
        default=True,
        description="是否启用每日定时推送。",
        json_schema_extra={"label": "定时推送", "order": 2},
    )
    push_format: Literal["text", "image"] = Field(
        default="text",
        description="推送格式：text（文字新闻列表）或 image（每日封面图片）。",
        json_schema_extra={
            "hint": "选择 image 时推送每日封面图，选择 text 时推送文字新闻列表。",
            "label": "推送格式",
            "order": 6,
        },
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        """规范化推送格式字段，非法值回退到 text。"""
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "text"


class GoldPriceApiConfig(ApiConfig):
    """黄金价格 API 配置（路径：/v2/gold-price，无参数）。"""

    __ui_label__: ClassVar[str] = "黄金价格"
    __ui_icon__: ClassVar[str] = "coins"
    __ui_order__: ClassVar[int] = 4

    name: str = Field(
        default="gold_price",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/gold_price"],
        description="触发关键词列表，必须以 / 开头。",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，大小写不敏感。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/gold_price",
        },
    )
    push_format: Literal["text", "image"] = Field(
        default="image",
        description="推送格式：text（文字列表）或 image（长图）。",
        json_schema_extra={"label": "推送格式", "order": 6},
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "image"


class GasPriceApiConfig(ApiConfig):
    """汽油价格 API 配置（路径：/v2/gas-price，参数：region=<城市名>）。"""

    __ui_label__: ClassVar[str] = "汽油价格"
    __ui_icon__: ClassVar[str] = "fuel"
    __ui_order__: ClassVar[int] = 5

    name: str = Field(
        default="gas_price",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/gas_price"],
        description="触发关键词列表，必须以 / 开头。用法：/gas_price <城市名>",
        json_schema_extra={
            "hint": "发送命令时在关键词后加城市名，例如：/gas_price 北京",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/gas_price",
        },
    )
    push_format: Literal["text", "image"] = Field(
        default="text",
        description="推送格式：text（文字表格）或 image（图片）。",
        json_schema_extra={
            "hint": "选择 image 时推送渲染后的油价图片，选择 text 时推送文字表格。",
            "label": "推送格式",
            "order": 6,
        },
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        """规范化推送格式字段，非法值回退到 text。"""
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "text"


class AiNewsApiConfig(ApiConfig):
    """AI 资讯快报 API 配置。"""

    __ui_label__: ClassVar[str] = "AI 资讯快报"
    __ui_icon__: ClassVar[str] = "bot"
    __ui_order__: ClassVar[int] = 6

    name: str = Field(
        default="ai_news",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/ai_news", "/ai"],
        description="触发关键词列表，必须以 / 开头。用法：/ai_news [YYYY-MM-DD] [all]",
        json_schema_extra={
            "hint": "支持可选日期参数 YYYY-MM-DD，也支持 all 参数请求全部日期。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/ai_news",
        },
    )
    push_format: Literal["text", "image"] = Field(
        default="image",
        description="推送格式：text（文字列表）或 image（长图）。",
        json_schema_extra={"label": "推送格式", "order": 6},
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "image"


class TodayInHistoryApiConfig(ApiConfig):
    """历史上的今天 API 配置。"""

    __ui_label__: ClassVar[str] = "历史上的今天"
    __ui_icon__: ClassVar[str] = "history"
    __ui_order__: ClassVar[int] = 7

    name: str = Field(
        default="today_in_history",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/today_history", "/history_today"],
        description="触发关键词列表，必须以 / 开头。用法：/today_history [YYYY-MM-DD]",
        json_schema_extra={
            "hint": "支持可选日期参数 YYYY-MM-DD，不填则按接口默认返回当天数据。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/today_history",
        },
    )
    push_format: Literal["text", "image"] = Field(
        default="image",
        description="推送格式：text（文字列表）或 image（长图）。",
        json_schema_extra={"label": "推送格式", "order": 6},
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "image"


class ItNewsApiConfig(ApiConfig):
    """实时 IT 资讯 API 配置。"""

    __ui_label__: ClassVar[str] = "实时 IT 资讯"
    __ui_icon__: ClassVar[str] = "cpu"
    __ui_order__: ClassVar[int] = 8

    name: str = Field(
        default="it_news",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: List[str] = Field(
        default_factory=lambda: ["/it_news", "/it"],
        description="触发关键词列表，必须以 / 开头。用法：/it_news [limit]",
        json_schema_extra={
            "hint": "支持可选条数参数，范围 1-50，不填时使用接口默认值。",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/it_news",
        },
    )
    push_format: Literal["text", "image"] = Field(
        default="image",
        description="推送格式：text（文字列表）或 image（长图）。",
        json_schema_extra={"label": "推送格式", "order": 6},
    )

    @field_validator("push_format", mode="before")
    @classmethod
    def _normalize_push_format(cls, value: Any) -> str:
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "image"


class Daily60sPluginConfig(PluginConfigBase):
    """每日速读插件完整配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    message_server: MessageServerConfig = Field(default_factory=MessageServerConfig)
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    daily_news: DailyNewsApiConfig = Field(default_factory=DailyNewsApiConfig)
    gold_price: GoldPriceApiConfig = Field(default_factory=GoldPriceApiConfig)
    gas_price: GasPriceApiConfig = Field(default_factory=GasPriceApiConfig)
    ai_news: AiNewsApiConfig = Field(default_factory=AiNewsApiConfig)
    today_in_history: TodayInHistoryApiConfig = Field(default_factory=TodayInHistoryApiConfig)
    it_news: ItNewsApiConfig = Field(default_factory=ItNewsApiConfig)

    @property
    def apis(self) -> List[ApiConfig]:
        """返回所有 API 配置列表，供 plugin.py 和 scheduler.py 统一迭代。"""
        ordered_api_names = [api_name for api_name in API_REGISTRY if hasattr(self, api_name)]
        return [getattr(self, api_name) for api_name in ordered_api_names]
