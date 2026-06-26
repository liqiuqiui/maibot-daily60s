"""delivery.py 测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from plugins.daily60s.delivery import deliver_fetch_result, resolve_fetch_result
from plugins.daily60s.fetcher import FetchResult


def create_mock_ctx(should_fail: bool = False):
    """创建模拟的 PluginContext"""
    ctx = Mock()
    ctx.logger = Mock()
    ctx.logger.warning = Mock()
    ctx.logger.info = Mock()
    ctx.logger.error = Mock()

    # 模拟 chat.get_stream_by_group_id 和 get_stream_by_user_id
    if should_fail:
        ctx.chat.get_stream_by_group_id = AsyncMock(return_value=None)
        ctx.chat.get_stream_by_user_id = AsyncMock(return_value=None)
    else:
        ctx.chat.get_stream_by_group_id = AsyncMock(return_value={"stream_id": "group_10001"})
        ctx.chat.get_stream_by_user_id = AsyncMock(return_value={"stream_id": "user_10001"})

    # 模拟 send.text 和 send.image
    if should_fail:
        ctx.send.text = AsyncMock(side_effect=RuntimeError("send text failed"))
        ctx.send.image = AsyncMock(side_effect=RuntimeError("send image failed"))
    else:
        ctx.send.text = AsyncMock(return_value=True)
        ctx.send.image = AsyncMock(return_value=True)

    return ctx


@pytest.mark.asyncio
async def test_resolve_fetch_result_text():
    """测试解析文本结果"""
    result = FetchResult(content="hello world")
    content = await resolve_fetch_result(result)
    assert content == "hello world"


@pytest.mark.asyncio
async def test_resolve_fetch_result_html_with_render_fn():
    """测试解析 HTML 结果（提供渲染函数）"""
    result = FetchResult(content="", html="<p>hello</p>")
    render_fn = AsyncMock(return_value="base64_image_data")

    content = await resolve_fetch_result(result, render_fn=render_fn)

    assert content == "base64_image_data"
    render_fn.assert_called_once_with("<p>hello</p>")


@pytest.mark.asyncio
async def test_resolve_fetch_result_html_without_render_fn():
    """测试解析 HTML 结果（未提供渲染函数）"""
    result = FetchResult(content="", html="<p>hello</p>")

    with pytest.raises(RuntimeError, match="当前消息需要 HTML 渲染，但未提供 render_fn"):
        await resolve_fetch_result(result)


@pytest.mark.asyncio
async def test_deliver_fetch_result_text_to_group():
    """测试发送文本到群"""
    ctx = create_mock_ctx()
    result = FetchResult(content="hello group")

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="group",
        target_id="10001",
        result=result,
    )

    # 验证获取了群的 stream_id
    ctx.chat.get_stream_by_group_id.assert_called_once_with("10001")
    # 验证发送了文本
    ctx.send.text.assert_called_once_with(text="hello group", stream_id="group_10001")


@pytest.mark.asyncio
async def test_deliver_fetch_result_text_to_user():
    """测试发送文本到用户"""
    ctx = create_mock_ctx()
    result = FetchResult(content="hello user")

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="user",
        target_id="20001",
        result=result,
    )

    # 验证获取了用户的 stream_id
    ctx.chat.get_stream_by_user_id.assert_called_once_with("20001")
    # 验证发送了文本
    ctx.send.text.assert_called_once_with(text="hello user", stream_id="user_10001")


@pytest.mark.asyncio
async def test_deliver_fetch_result_image_to_group():
    """测试发送图片到群"""
    ctx = create_mock_ctx()
    result = FetchResult(content="base64_data", is_image=True)

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="group",
        target_id="10001",
        result=result,
    )

    # 验证获取了群的 stream_id
    ctx.chat.get_stream_by_group_id.assert_called_once_with("10001")
    # 验证发送了图片
    ctx.send.image.assert_called_once_with(image_data="base64_data", stream_id="group_10001")


@pytest.mark.asyncio
async def test_deliver_fetch_result_image_to_user():
    """测试发送图片到用户"""
    ctx = create_mock_ctx()
    result = FetchResult(content="base64_data", is_image=True)

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="user",
        target_id="20001",
        result=result,
    )

    # 验证获取了用户的 stream_id
    ctx.chat.get_stream_by_user_id.assert_called_once_with("20001")
    # 验证发送了图片
    ctx.send.image.assert_called_once_with(image_data="base64_data", stream_id="user_10001")


@pytest.mark.asyncio
async def test_deliver_fetch_result_when_stream_not_found():
    """测试聊天流不存在的情况"""
    ctx = create_mock_ctx(should_fail=True)
    result = FetchResult(content="hello")

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="group",
        target_id="10001",
        result=result,
    )

    # 验证记录了警告
    ctx.logger.warning.assert_called_once()
    # 验证没有发送消息
    ctx.send.text.assert_not_called()
    ctx.send.image.assert_not_called()


@pytest.mark.asyncio
async def test_deliver_fetch_result_html_to_group():
    """测试发送 HTML 内容到群（需要渲染）"""
    ctx = create_mock_ctx()
    result = FetchResult(content="", html="<p>hello</p>")
    render_fn = AsyncMock(return_value="rendered_base64")

    await deliver_fetch_result(
        ctx=ctx,
        target_kind="group",
        target_id="10001",
        result=result,
        render_fn=render_fn,
    )

    # 验证调用了渲染函数
    render_fn.assert_called_once_with("<p>hello</p>")
    # 验证获取了群的 stream_id
    ctx.chat.get_stream_by_group_id.assert_called_once_with("10001")
    # 验证发送了图片（HTML 渲染后是图片）
    ctx.send.image.assert_called_once_with(image_data="rendered_base64", stream_id="group_10001")
