"""每日速读插件 — 数据源 HTTP 拉取与内容解析。

API_REGISTRY 硬编码所有已知接口的路径、参数定义和格式化器，不对外暴露为可配置项。
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import logging

import aiohttp

LOGGER = logging.getLogger("daily60s.fetcher")


@dataclass
class FetchResult:
    """拉取结果。

    Attributes:
        content: 文本内容或图片 base64 字符串。
        is_image: 为 True 时 content 是 base64 图片，应调用 send.image 发送。
    """

    content: str
    is_image: bool = False


@dataclass(frozen=True)
class ApiDefinition:
    """单个 API 的硬编码定义，不可通过配置修改。

    Attributes:
        path: API 路径，拼接在 base_url 后构成完整请求 URL。
        formatter: 响应格式化器标识。
        param_names: 从用户消息空格分割后依次提取的 URL 查询参数名列表。
                     例如 ["city"] 表示命令后第一个词作为 city 参数。
    """

    path: str
    formatter: str
    param_names: list[str] = field(default_factory=list)


# 所有已支持的 API 定义，键与 ApiConfig.name 对应
API_REGISTRY: dict[str, ApiDefinition] = {
    "daily_news": ApiDefinition(
        path="/v2/60s",
        formatter="60s",
        param_names=[],
    ),
    "gold_price": ApiDefinition(
        path="/v2/gold-price",
        formatter="gold_price",
        param_names=[],
    ),
    "gas_price": ApiDefinition(
        path="/v2/gas-price",
        formatter="gas_price",
        param_names=["city"],
    ),
}


class Fetcher:
    """异步 HTTP 数据源拉取器。

    Args:
        timeout: HTTP 请求超时秒数。
    """

    def __init__(self, timeout: int) -> None:
        self._timeout = timeout

    async def fetch(
        self,
        api_name: str,
        base_urls: list[str],
        params: dict[str, str] | None = None,
        push_format: str = "text",
    ) -> FetchResult:
        """从数据源拉取指定 API 的内容。

        按顺序尝试 base_urls，某个成功则直接返回，全部失败才抛出异常。

        Args:
            api_name: API 标识，对应 API_REGISTRY 的键。
            base_urls: 按优先级排列的根地址列表。
            params: 附加到请求 URL 的查询参数字典。
            push_format: 推送格式，"text" 或 "image"，仅 daily_news 支持 image。

        Returns:
            FetchResult: 拉取结果，包含内容和是否为图片的标识。

        Raises:
            RuntimeError: api_name 未知或所有 base_url 均请求失败时抛出。
        """
        definition = API_REGISTRY.get(api_name)
        if definition is None:
            raise RuntimeError(f"未知 API：'{api_name}'，请检查 API_REGISTRY")

        if not base_urls:
            raise RuntimeError("base_urls 为空，无法发起请求")

        last_error: Exception = RuntimeError("未知错误")
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        for base_url in base_urls:
            url = base_url.rstrip("/") + definition.path
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params or {}) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"HTTP {resp.status}")
                        content_type = resp.content_type or ""
                        if "json" in content_type:
                            data = await resp.json(content_type=None)
                        else:
                            data = (await resp.text()).strip()
                return await self._format(data, definition, params, push_format)
            except Exception as exc:
                LOGGER.warning("请求 %s 失败（%s），尝试下一个数据源", url, exc)
                last_error = exc

        raise RuntimeError(f"API '{api_name}' 所有数据源均请求失败") from last_error

    async def _format(
        self,
        data: Any,
        definition: ApiDefinition,
        params: dict[str, str] | None,
        push_format: str = "text",
    ) -> FetchResult:
        """根据 definition.formatter 将响应数据转换为 FetchResult。

        Args:
            data: 已解析的响应数据（dict、list 或 str）。
            definition: API 硬编码定义。
            params: 本次请求携带的参数，供部分格式化器使用。
            push_format: "text" 或 "image"，仅 daily_news 支持 image。

        Returns:
            FetchResult: 拉取结果。
        """
        if definition.formatter == "60s":
            return await self._format_60s(data, push_format)
        if definition.formatter == "gold_price":
            return self._format_gold_price(data)
        if definition.formatter == "gas_price":
            return self._format_gas_price(data, params)
        return self._format_auto(data, definition.path)

    # ── 专用格式化器 ──────────────────────────────────────────────────────────

    async def _format_60s(self, data: Any, push_format: str = "text") -> FetchResult:
        """格式化 /v2/60s 每日新闻响应。

        push_format 为 "image" 时下载封面图并以 base64 返回；否则返回文本。
        """
        if not isinstance(data, dict):
            return FetchResult(content=str(data))

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return FetchResult(content=str(data))

        if push_format == "image":
            image_url: str = inner.get("image", "")
            if image_url:
                try:
                    b64 = await self._download_image_as_base64(image_url)
                    return FetchResult(content=b64, is_image=True)
                except Exception as exc:
                    LOGGER.warning("图片下载失败（%s），回退到文本模式", exc)
            # 图片不可用时回退文本

        date = inner.get("date", "")
        news: list[Any] = inner.get("news", [])
        tip: str = inner.get("tip", "")
        lunar: str = inner.get("lunar_date", "")

        lines: list[str] = []
        if date:
            header = f"📰 {date}"
            if lunar:
                header += f"  {lunar}"
            lines.append(header)
            lines.append("")

        for i, item in enumerate(news, 1):
            lines.append(f"{i}. {item}")

        if tip:
            lines.append("")
            lines.append(f"💡 {tip}")

        return FetchResult(content="\n".join(lines) if lines else str(data))

    async def _download_image_as_base64(self, url: str) -> str:
        """下载图片并返回 base64 编码字符串。"""
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"图片下载返回 HTTP {resp.status}")
                raw = await resp.read()
                return base64.b64encode(raw).decode()

    def _format_gold_price(self, data: Any) -> FetchResult:
        """格式化 /v2/gold-price 黄金价格响应。"""
        if not isinstance(data, dict):
            return str(data)

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return str(data)

        date: str = inner.get("date", "")
        metals: list[Any] = inner.get("metals", [])

        lines: list[str] = []
        if date:
            lines.append(f"💰 黄金价格  {date}")
            lines.append("")

        for metal in metals:
            if not isinstance(metal, dict):
                continue
            name = metal.get("name", "")
            today = metal.get("today_price", "")
            sell = metal.get("sell_price", "")
            high = metal.get("high_price", "")
            low = metal.get("low_price", "")
            unit = metal.get("unit", "元/克")
            updated = metal.get("updated", "")

            line = f"▸ {name}：今日 {today} / 卖出 {sell}  最高 {high} 最低 {low}  {unit}"
            if updated:
                # 只保留时分秒部分
                time_part = updated.split(" ")[-1] if " " in updated else updated
                line += f"  (更新 {time_part})"
            lines.append(line)

        return FetchResult(content="\n".join(lines) if lines else str(data))

    def _format_gas_price(self, data: Any, params: dict[str, str] | None) -> FetchResult:
        """格式化 /v2/gas-price 汽油价格响应。"""
        if not isinstance(data, dict):
            return FetchResult(content=str(data))

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return FetchResult(content=str(data))

        date: str = inner.get("date", "")
        city = (params or {}).get("city", "")

        lines: list[str] = []
        title = f"⛽ 汽油价格  {date}" if date else "⛽ 汽油价格"
        if city:
            title += f"  [{city}]"
        lines.append(title)
        lines.append("")

        # 支持单城市结构（province 字段）和全省列表结构（provinces/list 字段）
        province_data: dict[str, Any] | None = None
        if "province" in inner:
            province_data = inner
        elif city:
            # 尝试从列表里找匹配的城市
            for key in ("provinces", "list", "data"):
                lst = inner.get(key, [])
                if isinstance(lst, list):
                    for item in lst:
                        if isinstance(item, dict) and city in str(item.get("name", "")):
                            province_data = item
                            break
                if province_data:
                    break

        if province_data:
            name = province_data.get("name") or province_data.get("province", "")
            p92 = province_data.get("p92") or province_data.get("92", "")
            p95 = province_data.get("p95") or province_data.get("95", "")
            p98 = province_data.get("p98") or province_data.get("98", "")
            diesel = province_data.get("diesel") or province_data.get("0", "")
            if name:
                lines.append(f"地区：{name}")
            if p92:
                lines.append(f"92号汽油：{p92} 元/升")
            if p95:
                lines.append(f"95号汽油：{p95} 元/升")
            if p98:
                lines.append(f"98号汽油：{p98} 元/升")
            if diesel:
                lines.append(f"0号柴油：{diesel} 元/升")
        else:
            # 全省列表，逐行列出
            for key in ("provinces", "list"):
                lst = inner.get(key, [])
                if isinstance(lst, list) and lst:
                    for item in lst:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name", item.get("province", ""))
                        p92 = item.get("p92", item.get("92", ""))
                        p95 = item.get("p95", item.get("95", ""))
                        diesel = item.get("diesel", item.get("0", ""))
                        lines.append(f"{name}  92:{p92}  95:{p95}  柴:{diesel}")
                    break
            else:
                LOGGER.warning("gas_price 响应结构未知，返回原始内容")
                return FetchResult(content=str(data))

        return FetchResult(content="\n".join(lines))

    def _format_auto(self, data: Any, path: str) -> FetchResult:
        """通用格式化器：优先读取常见字段，否则返回原始内容。"""
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

        LOGGER.warning("API '%s' 的响应结构无法识别，返回原始内容", path)
        return FetchResult(content=str(data))
