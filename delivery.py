"""daily60s 共用投递辅助。"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Literal

from .fetcher import FetchResult
from .sender import OneBotSender

TargetKind = Literal["group", "user"]
RenderFn = Callable[[str], Coroutine[Any, Any, str]]


async def resolve_fetch_result(result: FetchResult, render_fn: RenderFn | None = None) -> str:
    """将 FetchResult 解析成最终可发送内容。"""

    # fetcher 不直接依赖插件上下文，它只返回“文本 / 图片 base64 / 待渲染 HTML”三种中间态。
    # 这里把 HTML 渲染这一步补上，得到最终可投递的字符串内容。
    if result.html:
        if render_fn is None:
            raise RuntimeError("当前消息需要 HTML 渲染，但未提供 render_fn")
        return await render_fn(result.html)
    return result.content


async def deliver_fetch_result(
    sender: OneBotSender,
    target_kind: TargetKind,
    target_id: int,
    result: FetchResult,
    render_fn: RenderFn | None = None,
) -> None:
    """向群聊或私聊发送统一 FetchResult。"""

    # 先把结果解析成最终消息体，再根据目标类型和图片标记走不同 sender 方法。
    content = await resolve_fetch_result(result, render_fn=render_fn)
    if target_kind == "group":
        if result.is_image:
            await sender.send_group_image(target_id, content)
        else:
            await sender.send_group(target_id, content)
        return

    if result.is_image:
        await sender.send_user_image(target_id, content)
    else:
        await sender.send_user(target_id, content)
