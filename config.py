"""每日速读插件配置模型"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, cast

import re

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator

_PUSH_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

SUPPORTED_CONFIG_VERSION = "1.4.0"
ApiName = Literal["daily_news", "gold_price", "gas_price"]
VALID_API_NAMES: tuple[ApiName, ...] = ("daily_news", "gold_price", "gas_price")


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


def _normalize_push_time_value(value: Any) -> str:
    """规范化推送时间字段"""
    normalized_value = _normalize_string(value)
    return normalized_value or "08:00"


class BaseApiConfig(PluginConfigBase):
    """单个 API 的可配置部分基类
    API 路径、请求参数和格式化器均由代码硬编码（见 fetcher.py API_REGISTRY），
    此处只保存用户可调整的字段"""

    name: str = Field(
        default="",
        description="API 标识，对应代码内 API_REGISTRY 的键，不可更改",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    enabled: bool = Field(
        default=True,
        description="是否启用命令调用此 API",
        json_schema_extra={"label": "启用", "order": 0},
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="触发关键词列表，必须以 / 开头，消息第一个词与关键词精确匹配时触发",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，例如 /60s大小写不敏感",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/60s",
        },
    )

    @field_validator("keywords", mode="before")
    @classmethod
    def _normalize_keywords(cls, value: Any) -> list[str]:
        """规范化关键词列表，过滤不以 / 开头的项"""
        raw = _normalize_string_list(value)
        valid = [k for k in raw if k.startswith("/")]
        return valid


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
        default=SUPPORTED_CONFIG_VERSION,
        description="当前配置结构版本",
        json_schema_extra={"disabled": True, "hidden": True, "label": "配置版本", "order": 99},
    )

    @field_validator("config_version", mode="before")
    @classmethod
    def _normalize_config_version(cls, value: Any) -> str:
        normalized_value = _normalize_string(value)
        return normalized_value or SUPPORTED_CONFIG_VERSION


class FetchConfig(PluginConfigBase):
    """数据源拉取配置"""

    __ui_label__: ClassVar[str] = "数据源"
    __ui_icon__: ClassVar[str] = "globe"
    __ui_order__: ClassVar[int] = 1

    base_urls: list[str] = Field(
        default_factory=lambda: ["https://60s.viki.moe"],
        description="API 根地址列表，按顺序尝试，前一个失败时自动切换到下一个",
        json_schema_extra={
            "hint": "填写多个地址可实现冗余回退，例如自建实例与官方实例并列",
            "label": "数据源地址列表",
            "order": 9,
            "placeholder": "https://60s.viki.moe",
        },
    )

    timeout: int = Field(
        default=10,
        description="HTTP 请求超时秒数",
        json_schema_extra={
            "hint": "超过该时长未收到响应时视为请求失败，自动切换下一个 base_url",
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
    def _normalize_base_urls(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)


class DailyNewsApiConfig(BaseApiConfig):
    """每日60秒 API 配置（路径：/v2/60s，无参数）"""

    __ui_label__: ClassVar[str] = "每日60秒"
    __ui_icon__: ClassVar[str] = "newspaper"
    __ui_order__: ClassVar[int] = 3

    name: str = Field(
        default="daily_news",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: list[str] = Field(
        default_factory=lambda: ["/60s", "/daily60s"],
        description="触发关键词列表，必须以 / 开头",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，大小写不敏感",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/60s",
        },
    )


class GoldPriceApiConfig(BaseApiConfig):
    """黄金价格 API 配置（路径：/v2/gold-price，无参数）"""

    __ui_label__: ClassVar[str] = "黄金价格"
    __ui_icon__: ClassVar[str] = "coins"
    __ui_order__: ClassVar[int] = 4

    name: str = Field(
        default="gold_price",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: list[str] = Field(
        default_factory=lambda: ["/gold_price"],
        description="触发关键词列表，必须以 / 开头",
        json_schema_extra={
            "hint": "所有关键词必须以 / 开头，大小写不敏感",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/gold_price",
        },
    )


class GasPriceApiConfig(BaseApiConfig):
    """汽油价格 API 配置（路径：/v2/gas-price，参数：region=<城市名>）"""

    __ui_label__: ClassVar[str] = "汽油价格"
    __ui_icon__: ClassVar[str] = "fuel"
    __ui_order__: ClassVar[int] = 5

    name: str = Field(
        default="gas_price",
        json_schema_extra={"disabled": True, "hidden": True, "label": "API 标识", "order": 99},
    )
    keywords: list[str] = Field(
        default_factory=lambda: ["/gas_price"],
        description="触发关键词列表，必须以 / 开头用法：/gas_price <城市名>",
        json_schema_extra={
            "hint": "发送命令时在关键词后加城市名，例如：/gas_price 北京",
            "label": "触发关键词",
            "order": 1,
            "placeholder": "例如：/gas_price",
        },
    )


class BatchPushConfig(PluginConfigBase):
    """批量推送配置"""

    __ui_label__ = "批量推送配置"
    __ui_order__ = 2

    enabled: bool = Field(default=True, description="是否启用该组任务")
    apis: list[ApiName] = Field(
        default_factory=lambda: ["daily_news"],
        description="推送 API 列表，使用 API_REGISTRY 的 key",
    )
    schedule_push: bool = Field(default=False, description="是否开启定时推送")
    groups_type: Literal["whitelist", "blacklist"] = Field(default="whitelist", description="推送群组类型")
    groups: list[str] = Field(default=[], description="推送目标群组")
    users_type: Literal["whitelist", "blacklist"] = Field(default="whitelist", description="推送用户类型")
    users: list[str] = Field(default=[], description="推送用户")
    push_type: Literal["text", "image"] = Field(default="image", description="推送内容类型")
    push_time: str = Field(default="08:00", description="推送时间，格式：HH:MM")

    @field_validator("apis", mode="before")
    @classmethod
    def _normalize_apis(cls, value: Any) -> list[ApiName]:
        """规范化推送 API 列表，过滤空值与重复项，并校验 API key"""
        raw_values = _normalize_string_list(value)
        if not raw_values:
            raise ValueError("batch_push_config.apis 不能为空")

        invalid_values = [item for item in raw_values if item not in VALID_API_NAMES]
        if invalid_values:
            valid_values = ", ".join(VALID_API_NAMES)
            raise ValueError(f"batch_push_config.apis 包含未知 API：{', '.join(invalid_values)}可用值：{valid_values}")

        return cast(list[ApiName], raw_values)

    @field_validator("groups", mode="before")
    @classmethod
    def _normalize_groups(cls, value: Any) -> list[str]:
        """规范化推送群组列表"""
        return _normalize_string_list(value)

    @field_validator("users", mode="before")
    @classmethod
    def _normalize_users(cls, value: Any) -> list[str]:
        """规范化推送用户列表"""
        return _normalize_string_list(value)

    @field_validator("push_time", mode="before")
    @classmethod
    def _normalize_push_time(cls, value: Any) -> str:
        """规范化推送时间字段，非法值直接报错"""
        normalized_value = _normalize_push_time_value(value)
        if not _PUSH_TIME_RE.fullmatch(normalized_value):
            raise ValueError("push_time 必须是 HH:MM 格式，例如 08:00")
        return normalized_value

    @field_validator("push_type", mode="before")
    @classmethod
    def _normalize_push_type(cls, value: Any) -> str:
        """规范化推送格式字段，非法值回退到 text"""
        normalized = _normalize_string(value).lower()
        return normalized if normalized in ("text", "image") else "text"


class ApiConfig(PluginConfigBase):
    """api配置"""

    __ui_label__ = "api配置"

    daily_news: DailyNewsApiConfig = Field(default_factory=DailyNewsApiConfig)
    gold_price: GoldPriceApiConfig = Field(default_factory=GoldPriceApiConfig)
    gas_price: GasPriceApiConfig = Field(default_factory=GasPriceApiConfig)


class Daily60sPluginConfig(PluginConfigBase):
    """每日速读插件完整配置"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    batch_push_config: list[BatchPushConfig] = Field(default_factory=list)
    api_config: ApiConfig = Field(default_factory=ApiConfig)

    @property
    def apis(self) -> list[BaseApiConfig]:
        """返回所有 API 配置列表，供 plugin.py 和 scheduler.py 统一迭代"""
        return [self.api_config.daily_news, self.api_config.gold_price, self.api_config.gas_price]
