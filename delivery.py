"""daily60s 共用投递辅助。"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Literal

from maibot_sdk.context import PluginContext

from .fetcher import FetchResult

TargetKind = Literal["group", "user"]
RenderFn = Callable[[str], Coroutine[Any, Any, str]]


async def resolve_fetch_result(result: FetchResult, render_fn: RenderFn | None = None) -> str:
    """将 FetchResult 解析成最终可发送内容。"""

    # fetcher 不直接依赖插件上下文，它只返回"文本 / 图片 base64 / 待渲染 HTML"三种中间态。
    # 这里把 HTML 渲染这一步补上，得到最终可投递的字符串内容。
    if result.html:
        if render_fn is None:
            raise RuntimeError("当前消息需要 HTML 渲染，但未提供 render_fn")
        return await render_fn(result.html)
    return result.content


async def deliver_fetch_result(
    ctx: PluginContext,
    target_kind: TargetKind,
    target_id: str,
    result: FetchResult,
    render_fn: RenderFn | None = None,
) -> None:
    """向群聊或私聊发送统一 FetchResult。"""

    # 先把结果解析成最终消息体，再根据目标类型发送
    content = await resolve_fetch_result(result, render_fn=render_fn)

    # 获取 stream_id
    if target_kind == "group":
        stream_info = await ctx.chat.get_stream_by_group_id(target_id)
    else:
        stream_info = await ctx.chat.get_stream_by_user_id(target_id)

    if not stream_info:
        ctx.logger.warning("无法获取 %s=%s 的聊天流信息", target_kind, target_id)
        return

    stream_id = str(stream_info.get("stream_id")) if isinstance(stream_info, dict) else str(stream_info)

    # 判断是否为图片：原始结果是图片，或者 HTML 渲染后的结果
    is_image = result.is_image or (result.html and render_fn)

    # 发送消息
    if is_image:
        await ctx.send.image(image_data=content, stream_id=stream_id)
    else:
        await ctx.send.text(text=content, stream_id=stream_id)
