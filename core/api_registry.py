"""每日信息速递插件 — API 注册表与命令参数解析。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import re

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CommandUsageError(ValueError):
    """命令参数不符合接口要求时抛出。"""


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
    display_name: str
    menu_description: str
    request_params: list[RequestParamSpec] = field(default_factory=list)
    command_parser: CommandParser | None = None
    supports_image: bool = False
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
        display_name="每日新闻",
        menu_description="获取每日 60 秒新闻简报，适合快速了解今日热点。",
        request_params=[RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown")],
        command_parser=_parse_no_args,
        supports_image=True,
    ),
    "gold_price": ApiDefinition(
        path="/v2/gold-price",
        formatter="gold_price",
        display_name="黄金价格",
        menu_description="获取最新黄金价格行情。",
        request_params=[RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown")],
        command_parser=_parse_no_args,
        supports_image=True,
    ),
    "gas_price": ApiDefinition(
        path="/v2/fuel-price",
        formatter="gas_price",
        display_name="今日油价",
        menu_description="获取指定地区的汽油价格，需要提供地区参数。",
        request_params=[
            RequestParamSpec(name="region", description="地区名称", required=True),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_gas_price_args,
        supports_image=True,
        usage="<region>",
    ),
    "ai_news": ApiDefinition(
        path="/v2/ai-news",
        formatter="ai_news",
        display_name="AI 资讯快报",
        menu_description="获取 AI 行业资讯快报，可按日期查询或使用 all 获取全部。",
        request_params=[
            RequestParamSpec(name="date", description="新闻日期，可空，默认当天，格式：YYYY-MM-DD"),
            RequestParamSpec(name="all", description="是否获取所有日期，传 1 表示一次性拉取全部"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_ai_news_args,
        supports_image=True,
        usage="[YYYY-MM-DD] [all]",
    ),
    "today_in_history": ApiDefinition(
        path="/v2/today-in-history",
        formatter="today_in_history",
        display_name="历史上的今天",
        menu_description="获取指定日期或今天发生的历史事件。",
        request_params=[
            RequestParamSpec(name="date", description="指定 YYYY-MM-DD 格式的日期"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_today_in_history_args,
        supports_image=True,
        usage="[YYYY-MM-DD]",
    ),
    "it_news": ApiDefinition(
        path="/v2/it-news",
        formatter="it_news",
        display_name="实时 IT 资讯",
        menu_description="获取实时 IT 资讯，可指定返回条数。",
        request_params=[
            RequestParamSpec(name="limit", description="限制返回的条数，默认 20，最多 50"),
            RequestParamSpec(name="encoding", description="编码方式，支持 text/json/markdown"),
        ],
        command_parser=_parse_it_news_args,
        supports_image=True,
        usage="[limit]",
    ),
}
# 这里是 daily60s 的“单一事实来源”：
# - path 决定请求哪个 60s 接口
# - command_parser 决定命令参数如何映射到 query
# - formatter 决定响应如何变成文本/图片
# 后续继续接新模块时，优先只改这里和对应 formatter。
