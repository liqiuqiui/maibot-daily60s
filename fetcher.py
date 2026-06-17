"""每日速读插件 — 数据源 HTTP 拉取与内容解析。

API_REGISTRY 硬编码所有已知接口的路径、参数定义和格式化器，不对外暴露为可配置项。
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

from logging import Logger

import aiohttp


@dataclass
class FetchResult:
    """拉取结果。

    Attributes:
        content: 文本内容或图片 base64 字符串。
        is_image: 为 True 时 content 是 base64 图片，应调用 send.image 发送。
        html: 非空时表示需要调用方用 ctx.render.html2png 渲染，渲染后作为图片发送。
    """

    content: str
    is_image: bool = False
    html: str = ""


@dataclass(frozen=True)
class ApiDefinition:
    """单个 API 的硬编码定义，不可通过配置修改。

    Attributes:
        path: API 路径，拼接在 base_url 后构成完整请求 URL。
        formatter: 响应格式化器标识。
        param_names: 从用户消息空格分割后依次提取的 URL 查询参数名列表。
                     例如 ["region"] 表示命令后第一个词作为 region 参数。
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
        path="/v2/fuel-price",
        formatter="gas_price",
        param_names=["region"],
    ),
}


class Fetcher:
    """异步 HTTP 数据源拉取器。

    Args:
        timeout: HTTP 请求超时秒数。
    """

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
            self.logger.info(f"params={params}, url={url}")
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
                return await self._format(data, definition, push_format)
            except Exception as exc:
                self.logger.warning("请求 %s 失败（%s），尝试下一个数据源", url, exc)
                last_error = exc

        raise RuntimeError(f"API '{api_name}' 所有数据源均请求失败") from last_error

    async def _format(
        self,
        data: Any,
        definition: ApiDefinition,
        push_format: str = "text",
    ) -> FetchResult:
        """根据 definition.formatter 将响应数据转换为 FetchResult。

        Args:
            data: 已解析的响应数据（dict、list 或 str）。
            definition: API 硬编码定义。
            push_format: "text" 或 "image"，仅部分 formatter 支持 image。

        Returns:
            FetchResult: 拉取结果。
        """
        if definition.formatter == "60s":
            return await self._format_60s(data, push_format)
        if definition.formatter == "gold_price":
            return await self._format_gold_price(data)
        if definition.formatter == "gas_price":
            return await self._format_gas_price(data, push_format)
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
                    self.logger.warning("图片下载失败（%s），回退到文本模式", exc)
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

    async def _format_gold_price(self, data: Any) -> FetchResult:
        """格式化 /v2/gold-price 黄金价格响应。"""

        if not isinstance(data, dict):
            return FetchResult(content=str(data))

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return FetchResult(content=str(data))

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

    async def _format_gas_price(
        self,
        response: Any,
        push_format: str = "text",
    ) -> FetchResult:
        """格式化 /v2/gas-price 汽油价格响应。

        支持文本和图片两种格式，通过 push_format 参数控制。
        """
        if not response.get("code") == 200:
            return FetchResult(content=response.get("message") or "数据获取失败")

        data = response.get("data", {})
        region: str = data.get("region", "")
        items: list[Any] = data.get("items", [])
        trend: dict[str, Any] = data.get("trend", {})
        updated: str = data.get("updated", "")

        if not items:
            return FetchResult(content="暂无价格数据")

        if push_format == "image":
            html = self._build_gas_price_html(region, items, trend, updated)
            return FetchResult(content="", is_image=True, html=html)

        # 文本表格格式 - 纯空格对齐
        def display_width(s: str) -> int:
            return sum(2 if ord(c) > 127 else 1 for c in s)

        col1_header = "油品类型"
        col2_header = "价格(元/升)"
        col1_w = max(display_width(col1_header), *(display_width(it.get("name", "")) for it in items))

        lines = [f"⛽ {region}今日油价", f"更新时间：{updated}", ""]

        def pad(s: str, width: int) -> str:
            return s + " " * (width - display_width(s))

        lines.append(f"{pad(col1_header, col1_w)}  {col2_header}")
        for item in items:
            name: str = item.get("name", "")
            price: float = item.get("price", 0)
            lines.append(f"{pad(name, col1_w)}  {price:.2f}")

        if trend:
            desc: str = trend.get("description", "")
            if desc:
                lines.append("")
                lines.append(f"💡 {desc}")

        return FetchResult(content="\n".join(lines))

    @staticmethod
    def _build_gas_price_html(
        region: str,
        items: list[Any],
        trend: dict[str, Any],
        updated: str,
    ) -> str:
        """构建油价卡片 HTML，供调用方通过 ctx.render.html2png 渲染为图片。"""
        desc: str = trend.get("description", "") if trend else ""

        rows_html = "\n".join(
            f"""<tr>
                <td>{item.get("name", "")}</td>
                <td class="price">{item.get("price", 0):.2f}</td>
                <td class="unit">元/升</td>
            </tr>"""
            for item in items
        )

        tip_html = f'<div class="tip">💡 {desc}</div>' if desc else ""

        return f"""<!DOCTYPE html>
                    <html>
                        <head>
                            <meta charset="utf-8">
                            <style>
                            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                            body {{
                                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
                                background: #ffffff;
                                padding: 24px;
                                width: 420px;
                            }}
                            .title {{
                                font-size: 22px;
                                font-weight: 600;
                                color: #1a1a1a;
                                margin-bottom: 4px;
                            }}
                            .subtitle {{
                                font-size: 12px;
                                color: #999;
                                margin-bottom: 16px;
                            }}
                            table {{
                                width: 100%;
                                border-collapse: collapse;
                            }}
                            thead tr {{
                                border-bottom: 2px solid #e5e5e5;
                            }}
                            th {{
                                font-size: 13px;
                                color: #888;
                                font-weight: 500;
                                padding: 6px 0 10px 0;
                                text-align: left;
                            }}
                            th:not(:first-child) {{ text-align: right; }}
                            tbody tr {{
                                border-bottom: 1px solid #f0f0f0;
                            }}
                            tbody tr:last-child {{ border-bottom: none; }}
                            td {{
                                padding: 12px 0;
                                font-size: 16px;
                                color: #1a1a1a;
                            }}
                            td.price {{
                                text-align: right;
                                font-size: 18px;
                                font-weight: 600;
                                color: #e05030;
                            }}
                            td.unit {{
                                text-align: right;
                                font-size: 13px;
                                color: #999;
                                padding-left: 4px;
                                width: 40px;
                            }}
                            .tip {{
                                margin-top: 14px;
                                padding: 10px 12px;
                                background: #f9f6f0;
                                border-radius: 6px;
                                font-size: 12px;
                                color: #888;
                                line-height: 1.6;
                            }}
                            </style>
                        </head>
                    <body>
                        <div class="title">⛽ {region}今日油价</div>
                        <div class="subtitle">更新时间：{updated}</div>
                        <table>
                            <thead>
                                <tr>
                                    <th>油品类型</th>
                                    <th>价格</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                        {tip_html}
                    </body>
                    </html>
                """

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

        self.logger.warning("API '%s' 的响应结构无法识别，返回原始内容", path)
        return FetchResult(content=str(data))
