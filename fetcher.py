"""每日信息速递插件 — 数据源 HTTP 拉取、命令参数解析与内容格式化。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from logging import Logger
from typing import Any

import base64
import re

import aiohttp

from .renderers import (
    build_ai_news_html,
    build_digest_html,
    build_digest_item_html,
    build_gas_price_html,
    build_gold_price_html,
    build_today_in_history_html,
)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CommandUsageError(ValueError):
    """命令参数不符合接口要求时抛出。"""


@dataclass
class FetchResult:
    """拉取结果。"""

    content: str
    is_image: bool = False
    html: str = ""


CommandParser = Callable[[list[str]], dict[str, str]]


@dataclass(frozen=True)
class RequestParamSpec:
    """接口请求参数声明。"""

    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class ApiDefinition:
    """单个 API 的硬编码定义。"""

    path: str
    formatter: str
    request_params: list[RequestParamSpec] = field(default_factory=list)
    command_parser: CommandParser | None = None
    supports_image: bool = False
    default_push_format: str = "text"
    default_keywords: list[str] = field(default_factory=list)
    default_schedule_push: bool = False
    usage: str = ""


def _ensure_no_extra_args(arg_tokens: list[str]) -> None:
    if arg_tokens:
        raise CommandUsageError("当前命令不接受参数")


def _parse_no_args(arg_tokens: list[str]) -> dict[str, str]:
    _ensure_no_extra_args(arg_tokens)
    return {}


def _parse_gas_price_args(arg_tokens: list[str]) -> dict[str, str]:
    if len(arg_tokens) != 1:
        raise CommandUsageError("汽油价格命令需要且仅接受一个地区参数")
    region = arg_tokens[0].strip()
    if not region:
        raise CommandUsageError("地区参数不能为空")
    return {"region": region}


def _parse_today_in_history_args(arg_tokens: list[str]) -> dict[str, str]:
    if not arg_tokens:
        return {}
    if len(arg_tokens) != 1:
        raise CommandUsageError("历史上的今天命令最多接受一个日期参数")
    date_value = arg_tokens[0].strip()
    if not _DATE_RE.match(date_value):
        raise CommandUsageError("日期参数必须为 YYYY-MM-DD 格式")
    return {"date": date_value}


def _parse_it_news_args(arg_tokens: list[str]) -> dict[str, str]:
    if not arg_tokens:
        return {}
    if len(arg_tokens) != 1:
        raise CommandUsageError("实时 IT 资讯命令最多接受一个条数参数")
    limit_text = arg_tokens[0].strip()
    if not limit_text.isdigit():
        raise CommandUsageError("limit 必须为正整数")
    limit_value = int(limit_text)
    if limit_value < 1 or limit_value > 50:
        raise CommandUsageError("limit 必须在 1 到 50 之间")
    return {"limit": str(limit_value)}


def _parse_ai_news_args(arg_tokens: list[str]) -> dict[str, str]:
    if len(arg_tokens) > 2:
        raise CommandUsageError("AI 资讯快报命令最多接受两个参数")

    params: dict[str, str] = {}
    for token in arg_tokens:
        normalized = token.strip()
        lowered = normalized.lower()
        if lowered == "all":
            params["all"] = "1"
            continue
        if _DATE_RE.match(normalized):
            params["date"] = normalized
            continue
        raise CommandUsageError("AI 资讯快报仅支持可选的 YYYY-MM-DD 日期参数和 all 参数")
    return params


def build_api_request_params(definition: ApiDefinition, arg_tokens: list[str]) -> dict[str, str]:
    """按 API registry 的命令解析规则，将命令位置参数转换为查询参数。"""

    # 所有命令参数都从 registry 的 command_parser 进入。
    # plugin/scheduler 不需要知道某个 API 是按位置参数、日期还是 limit 解析。
    parser = definition.command_parser or _parse_no_args
    return parser(arg_tokens)


def build_command_usage(command_token: str, definition: ApiDefinition) -> str:
    """构造命令用法提示。"""

    if definition.usage:
        return f"参数错误，用法：{command_token} {definition.usage}"
    return f"参数错误，用法：{command_token}"


API_REGISTRY: dict[str, ApiDefinition] = {
    "daily_news": ApiDefinition(
        path="/v2/60s",
        formatter="60s",
        request_params=[RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown")],
        command_parser=_parse_no_args,
        supports_image=True,
        default_push_format="text",
        default_keywords=["/60s", "/daily60s"],
        default_schedule_push=True,
    ),
    "gold_price": ApiDefinition(
        path="/v2/gold-price",
        formatter="gold_price",
        request_params=[RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown")],
        command_parser=_parse_no_args,
        supports_image=True,
        default_push_format="image",
        default_keywords=["/gold_price"],
    ),
    "gas_price": ApiDefinition(
        path="/v2/fuel-price",
        formatter="gas_price",
        request_params=[
            RequestParamSpec(name="region", description="地区名称", required=True),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_gas_price_args,
        supports_image=True,
        default_push_format="text",
        default_keywords=["/gas_price", "/gas"],
        usage="<region>",
    ),
    "ai_news": ApiDefinition(
        path="/v2/ai-news",
        formatter="ai_news",
        request_params=[
            RequestParamSpec(name="date", description="新闻日期，可空，默认当天，格式：YYYY-MM-DD"),
            RequestParamSpec(name="all", description="是否获取所有日期，传 1 表示一次性拉取全部"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_ai_news_args,
        supports_image=True,
        default_push_format="image",
        default_keywords=["/ai_news", "/ai"],
        usage="[YYYY-MM-DD] [all]",
    ),
    "today_in_history": ApiDefinition(
        path="/v2/today-in-history",
        formatter="today_in_history",
        request_params=[
            RequestParamSpec(name="date", description="指定 YYYY-MM-DD 格式的日期"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_today_in_history_args,
        supports_image=True,
        default_push_format="image",
        default_keywords=["/today_history", "/history_today"],
        usage="[YYYY-MM-DD]",
    ),
    "it_news": ApiDefinition(
        path="/v2/it-news",
        formatter="it_news",
        request_params=[
            RequestParamSpec(name="limit", description="限制返回的条数，默认 20，最多 50"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_it_news_args,
        supports_image=True,
        default_push_format="image",
        default_keywords=["/it_news", "/it"],
        usage="[limit]",
    ),
}
# 这里是 daily60s 的“单一事实来源”：
# - path 决定请求哪个 60s 接口
# - command_parser 决定命令参数如何映射到 query
# - formatter 决定响应如何变成文本/图片
# 后续继续接新模块时，优先只改这里和对应 formatter。


class Fetcher:
    """异步 HTTP 数据源拉取器。"""

    def __init__(self, logger: Logger, timeout: int) -> None:
        self._timeout = timeout
        self.logger = logger

    async def fetch(
        self,
        api_name: str,
        base_urls: list[str],
        params: dict[str, str] | None = None,
        push_format: str = "text",
    ) -> FetchResult:
        """从数据源拉取指定 API 的内容。"""

        definition = API_REGISTRY.get(api_name)
        if definition is None:
            raise RuntimeError(f"未知 API：'{api_name}'，请检查 API_REGISTRY")

        if not base_urls:
            raise RuntimeError("base_urls 为空，无法发起请求")

        last_error: Exception = RuntimeError("未知错误")
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        for base_url in base_urls:
            url = base_url.rstrip("/") + definition.path
            self.logger.info("daily60s 请求 url=%s params=%s", url, params)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params or {}) as response:
                        if response.status != 200:
                            raise RuntimeError(f"HTTP {response.status}")
                        content_type = response.content_type or ""
                        if "json" in content_type:
                            data = await response.json(content_type=None)
                        else:
                            data = (await response.text()).strip()
                # fetch 阶段只负责 HTTP 和基础解析，真正转成“可发内容”交给 formatter。
                return await self._format(data, definition, push_format)
            except Exception as exc:
                self.logger.warning("请求 %s 失败（%s），尝试下一个数据源", url, exc)
                last_error = exc

        raise RuntimeError(f"API '{api_name}' 所有数据源均请求失败") from last_error

    async def _format(self, data: Any, definition: ApiDefinition, push_format: str = "text") -> FetchResult:
        """根据 formatter 将响应数据转换为 FetchResult。"""

        # push_format 是用户偏好，但最终是否真能输出图片，还要看该接口是否 supports_image。
        effective_push_format = push_format
        if effective_push_format == "image" and not definition.supports_image:
            effective_push_format = "text"

        if definition.formatter == "60s":
            return await self._format_60s(data, effective_push_format)
        if definition.formatter == "gold_price":
            return await self._format_gold_price(data, effective_push_format)
        if definition.formatter == "gas_price":
            return await self._format_gas_price(data, effective_push_format)
        if definition.formatter == "ai_news":
            return await self._format_ai_news(data, effective_push_format)
        if definition.formatter == "today_in_history":
            return await self._format_today_in_history(data, effective_push_format)
        if definition.formatter == "it_news":
            return await self._format_it_news(data, effective_push_format)
        return self._format_auto(data, definition.path)

    async def _format_60s(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/60s 每日新闻响应。"""

        if not isinstance(data, dict):
            return FetchResult(content=str(data))

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return FetchResult(content=str(data))

        if push_format == "image":
            image_url = inner.get("image", "")
            if image_url:
                try:
                    b64 = await self._download_image_as_base64(image_url)
                    return FetchResult(content=b64, is_image=True)
                except Exception as exc:
                    self.logger.warning("图片下载失败（%s），回退到文本模式", exc)

        date_value = self._stringify(inner.get("date"))
        news = inner.get("news", [])
        tip = self._stringify(inner.get("tip"))
        lunar = self._stringify(inner.get("lunar_date"))

        lines: list[str] = []
        if date_value:
            header = f"📰 {date_value}"
            if lunar:
                header += f"  {lunar}"
            lines.append(header)
            lines.append("")

        if isinstance(news, list):
            for index, item in enumerate(news, 1):
                lines.append(f"{index}. {item}")

        if tip:
            lines.append("")
            lines.append(f"💡 {tip}")

        return FetchResult(content="\n".join(lines) if lines else str(data))

    async def _download_image_as_base64(self, url: str) -> str:
        """下载图片并返回 base64 编码字符串。"""

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"图片下载返回 HTTP {response.status}")
                raw = await response.read()
                return base64.b64encode(raw).decode()

    async def _format_gold_price(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/gold-price 黄金价格响应。"""

        if not isinstance(data, dict):
            return FetchResult(content=str(data))

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return FetchResult(content=str(data))

        date_value = self._stringify(inner.get("date"))
        metals = inner.get("metals", [])

        # 先整理成统一结构，后面文本和图片都复用这份中间数据，避免两套逻辑各算各的。
        normalized_metals: list[dict[str, str]] = []
        lines: list[str] = []
        if date_value:
            lines.append(f"💰 黄金价格  {date_value}")
            lines.append("")

        if isinstance(metals, list):
            for metal in metals:
                if not isinstance(metal, dict):
                    continue
                name = self._stringify(metal.get("name"))
                today = self._stringify(metal.get("today_price"))
                sell = self._stringify(metal.get("sell_price"))
                high = self._stringify(metal.get("high_price"))
                low = self._stringify(metal.get("low_price"))
                unit = self._stringify(metal.get("unit")) or "元/克"
                updated = self._stringify(metal.get("updated"))
                normalized_metals.append(
                    {
                        "name": name,
                        "today": today,
                        "sell": sell,
                        "high": high,
                        "low": low,
                        "unit": unit,
                        "updated": updated,
                    }
                )

                line = f"▸ {name}：今日 {today} / 卖出 {sell}  最高 {high} 最低 {low}  {unit}"
                if updated:
                    time_part = updated.split(" ")[-1] if " " in updated else updated
                    line += f"  (更新 {time_part})"
                lines.append(line)

        if push_format == "image":
            return FetchResult(
                content="",
                is_image=True,
                html=build_gold_price_html(date_value=date_value, metals=normalized_metals),
            )

        return FetchResult(content="\n".join(lines) if lines else str(data))

    async def _format_gas_price(self, response: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/fuel-price 汽油价格响应。"""

        if not isinstance(response, dict):
            raise RuntimeError("汽油价格响应格式非法：顶层必须为对象")

        if response.get("code") != 200:
            return FetchResult(content=self._stringify(response.get("message")) or "数据获取失败")

        data = response.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("汽油价格响应格式非法：data 必须为对象")

        region = self._stringify(data.get("region"))
        updated = self._stringify(data.get("updated"))
        trend = data.get("trend") or {}
        if not isinstance(trend, dict):
            raise RuntimeError("汽油价格响应格式非法：trend 必须为对象")

        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("汽油价格响应格式非法：items 必须为数组")

        # 对油价响应做严格结构校验。
        # 这里不做静默兜底，结构错了就直接抛异常，方便尽快暴露接口变化。
        items: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                raise RuntimeError("汽油价格响应格式非法：items 内元素必须为对象")
            name = self._stringify(item.get("name"))
            if not name:
                raise RuntimeError("汽油价格响应格式非法：油品名称不能为空")
            try:
                price = float(item.get("price") or 0)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("汽油价格响应格式非法：price 必须为数字") from exc
            items.append({"name": name, "price": price})

        if not items:
            return FetchResult(content="暂无价格数据")

        if push_format == "image":
            return FetchResult(content="", is_image=True, html=build_gas_price_html(region, items, trend, updated))

        def display_width(text: str) -> int:
            return sum(2 if ord(char) > 127 else 1 for char in text)

        col1_header = "油品类型"
        col2_header = "价格(元/升)"
        col1_width = max(display_width(col1_header), *(display_width(item["name"]) for item in items))

        def pad(text: str, width: int) -> str:
            return text + " " * (width - display_width(text))

        lines = [f"⛽ {region}今日油价", f"更新时间：{updated}", ""]
        lines.append(f"{pad(col1_header, col1_width)}  {col2_header}")
        for item in items:
            lines.append(f"{pad(item['name'], col1_width)}  {item['price']:.2f}")

        description = self._stringify(trend.get("description"))
        if description:
            lines.append("")
            lines.append(f"💡 {description}")

        return FetchResult(content="\n".join(lines))

    async def _format_ai_news(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/ai-news AI 资讯快报响应。"""

        payload = self._require_mapping(data, "AI 资讯快报响应")
        inner = self._require_mapping(payload.get("data"), "AI 资讯快报 data")
        news_items = self._require_list(inner.get("news"), "AI 资讯快报 news")
        date_value = self._stringify(inner.get("date"))

        normalized_items: list[dict[str, str]] = []
        for item in news_items:
            news = self._require_mapping(item, "AI 资讯条目")
            title = self._require_non_empty_text(news.get("title"), "AI 资讯条目 title")
            normalized_items.append(
                {
                    "title": title,
                    "detail": self._stringify(news.get("detail")) or self._stringify(news.get("description")),
                    "source": self._stringify(news.get("source")),
                    "date": self._stringify(news.get("date")),
                    "link": self._stringify(news.get("link")),
                }
            )

        if push_format == "image":
            return FetchResult(
                content="",
                is_image=True,
                html=build_ai_news_html(
                    date_text=date_value,
                    source_text="数据来源：60s API / AI 工具集等公开来源",
                    items=normalized_items,
                ),
            )

        lines = [f"🤖 AI 资讯快报  {date_value}".rstrip(), ""]
        for index, item in enumerate(normalized_items, 1):
            lines.append(f"{index}. {item['title']}")
            if item["source"]:
                lines.append(f"   来源：{item['source']}")
            if item["date"]:
                lines.append(f"   时间：{item['date']}")
            if item["detail"]:
                lines.append(f"   摘要：{item['detail']}")
            if item["link"]:
                lines.append(f"   链接：{item['link']}")
            lines.append("")
        return FetchResult(content="\n".join(lines).strip())

    async def _format_today_in_history(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/today-in-history 历史上的今天响应。"""

        payload = self._require_mapping(data, "历史上的今天响应")
        inner = self._require_mapping(payload.get("data"), "历史上的今天 data")
        history_items = self._require_list(inner.get("items"), "历史上的今天 items")

        date_value = self._stringify(inner.get("date"))
        month = self._stringify(inner.get("month"))
        day = self._stringify(inner.get("day"))
        date_display = date_value or f"{month}-{day}".strip("-")

        normalized_items: list[dict[str, str]] = []
        for item in history_items:
            history = self._require_mapping(item, "历史上的今天条目")
            title = self._require_non_empty_text(history.get("title"), "历史上的今天条目 title")
            normalized_items.append(
                {
                    "title": title,
                    "year": self._stringify(history.get("year")),
                    "description": self._stringify(history.get("description")),
                    "event_type": self._map_history_event_type(self._stringify(history.get("event_type"))),
                    "link": self._stringify(history.get("link")),
                }
            )

        if push_format == "image":
            return FetchResult(
                content="",
                is_image=True,
                html=build_today_in_history_html(date_display=date_display, items=normalized_items),
            )

        lines = [f"📜 历史上的今天  {date_display}".rstrip(), ""]
        for index, item in enumerate(normalized_items, 1):
            prefix = item["year"] or f"事件 {index}"
            lines.append(f"{index}. [{prefix}] {item['title']}")
            if item["event_type"]:
                lines.append(f"   类型：{item['event_type']}")
            if item["description"]:
                lines.append(f"   简述：{item['description']}")
            if item["link"]:
                lines.append(f"   链接：{item['link']}")
            lines.append("")
        return FetchResult(content="\n".join(lines).strip())

    async def _format_it_news(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/it-news 实时 IT 资讯响应。"""

        payload = self._require_mapping(data, "实时 IT 资讯响应")
        news_items = self._require_list(payload.get("data"), "实时 IT 资讯 data")

        normalized_items: list[dict[str, str]] = []
        for item in news_items:
            news = self._require_mapping(item, "实时 IT 资讯条目")
            title = self._require_non_empty_text(news.get("title"), "实时 IT 资讯条目 title")
            normalized_items.append(
                {
                    "title": title,
                    "description": self._stringify(news.get("description")),
                    "created": self._stringify(news.get("created")) or self._format_timestamp(news.get("created_at")),
                    "link": self._stringify(news.get("link")),
                }
            )

        if push_format == "image":
            item_blocks = [
                build_digest_item_html(
                    title=item["title"],
                    meta=[item["created"]],
                    summary=item["description"],
                )
                for item in normalized_items
            ]
            return FetchResult(
                content="",
                is_image=True,
                html=build_digest_html(
                    title="实时 IT 资讯",
                    date_text="持续更新",
                    source_text="数据来源：60s API / IT 之家",
                    item_blocks=item_blocks,
                ),
            )

        lines = ["💻 实时 IT 资讯", ""]
        for index, item in enumerate(normalized_items, 1):
            lines.append(f"{index}. {item['title']}")
            if item["created"]:
                lines.append(f"   时间：{item['created']}")
            if item["description"]:
                lines.append(f"   摘要：{item['description']}")
            if item["link"]:
                lines.append(f"   链接：{item['link']}")
            lines.append("")
        return FetchResult(content="\n".join(lines).strip())

    @staticmethod
    def _format_auto(data: Any, path: str) -> FetchResult:
        """通用格式化器。"""

        if isinstance(data, str):
            return FetchResult(content=data.strip())

        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                data = inner
            for key in ("news", "content", "text", "msg", "message"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return FetchResult(content=value.strip())
                if isinstance(value, list):
                    return FetchResult(content="\n".join(str(item) for item in value if item))

        return FetchResult(content=str(data))

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise RuntimeError(f"{field_name} 必须为对象")
        return value

    @staticmethod
    def _require_list(value: Any, field_name: str) -> list[Any]:
        if not isinstance(value, list):
            raise RuntimeError(f"{field_name} 必须为数组")
        return value

    @staticmethod
    def _require_non_empty_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"{field_name} 不能为空字符串")
        return value.strip()

    @staticmethod
    def _map_history_event_type(event_type: str) -> str:
        mapping = {
            "birth": "出生",
            "death": "逝世",
            "event": "事件",
        }
        return mapping.get(event_type, event_type)

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        if isinstance(value, (int, float)):
            timestamp = int(value)
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            try:
                from datetime import datetime

                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except (OSError, OverflowError, ValueError):
                return str(value)
        return Fetcher._stringify(value)
