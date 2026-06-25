import logging
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from plugins.daily60s.config import Daily60sPluginConfig
from plugins.daily60s.fetcher import FetchResult
from plugins.daily60s.scheduler import Scheduler


class DummyFetcher:
    def __init__(self, result: FetchResult):
        self.result = result

    async def fetch(self, **kwargs):
        return self.result


def create_mock_ctx(should_fail: bool = False):
    """创建模拟的 PluginContext"""
    ctx = Mock()
    ctx.logger = logging.getLogger("daily60s-test-ctx")

    # 模拟 chat.get_stream_by_group_id 和 get_stream_by_user_id
    if should_fail:
        ctx.chat.get_stream_by_group_id = AsyncMock(side_effect=RuntimeError("get stream failed"))
        ctx.chat.get_stream_by_user_id = AsyncMock(side_effect=RuntimeError("get stream failed"))
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
async def test_scheduler_marks_last_push_date_after_successful_push():
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")
    # 验证调用了 send.text
    ctx.send.text.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_does_not_mark_last_push_date_when_delivery_fails():
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]

    ctx = create_mock_ctx(should_fail=True)
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    assert "daily_news" not in scheduler._last_push_date


@pytest.mark.asyncio
async def test_scheduler_start_logs_enabled_schedule_count():
    config = Daily60sPluginConfig()
    config.daily_news.schedule_push = True
    config.daily_news.enabled = True
    config.gold_price.schedule_push = True
    config.gold_price.enabled = True
    config.ai_news.schedule_push = False

    logger = Mock()
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logger,
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    scheduler.start()
    await scheduler.stop()

    logger.info.assert_any_call("定时推送调度器已启动，当前启用 %d 条定时任务", 2)


@pytest.mark.asyncio
async def test_scheduler_do_push_with_empty_groups_and_users():
    """测试空群和用户的推送"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = []
    config.daily_news.push_users = []

    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=logger,
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    # 验证记录了跳过信息
    logger.info.assert_any_call("API '%s' 的 push_groups 和 push_users 均为空，跳过定时推送", "daily_news")
    # 验证没有发送消息
    ctx.send.text.assert_not_called()
    ctx.send.image.assert_not_called()
    # 验证没有标记推送日期
    assert "daily_news" not in scheduler._last_push_date


@pytest.mark.asyncio
async def test_scheduler_do_push_with_fetch_failure():
    """测试拉取失败的情况"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]

    class FailingFetcher:
        async def fetch(self, **kwargs):
            raise RuntimeError("fetch failed")

    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=logger,
        ctx=ctx,
        config=config,
        fetcher=FailingFetcher(),
    )

    await scheduler._do_push(config.daily_news)

    # 验证记录了拉取失败
    logger.exception.assert_called_once()
    # 验证没有发送消息
    ctx.send.text.assert_not_called()
    # 验证没有标记推送日期
    assert "daily_news" not in scheduler._last_push_date


@pytest.mark.asyncio
async def test_scheduler_do_push_with_image_result():
    """测试图片格式的推送"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]
    config.daily_news.push_format = "image"

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="image_data", is_image=True)),
    )

    await scheduler._do_push(config.daily_news)

    # 验证标记了推送日期
    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")
    # 验证发送了图片
    ctx.send.image.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_do_push_to_multiple_groups():
    """测试推送到多个群"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001", "10002", "10003"]

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    # 验证标记了推送日期
    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")
    # 验证发送了 3 次
    assert ctx.send.text.call_count == 3


@pytest.mark.asyncio
async def test_scheduler_do_push_to_multiple_users():
    """测试推送到多个用户"""
    config = Daily60sPluginConfig()
    config.daily_news.push_users = ["20001", "20002"]

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    # 验证标记了推送日期
    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")
    # 验证发送了 2 次
    assert ctx.send.text.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_do_push_to_groups_and_users():
    """测试同时推送到群和用户"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]
    config.daily_news.push_users = ["20001"]

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    # 验证标记了推送日期
    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")
    # 验证发送了 2 次（1 个群 + 1 个用户）
    assert ctx.send.text.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_do_push_partial_failure():
    """测试部分推送失败的情况"""
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001", "10002"]

    # 第一个群成功，第二个群失败
    call_count = 0
    original_send_text = AsyncMock(return_value=True)

    async def mock_send_text(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("send failed")
        return True

    ctx = create_mock_ctx()
    ctx.send.text = mock_send_text

    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await scheduler._do_push(config.daily_news)

    # 验证标记了推送日期（因为第一个群成功了）
    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_scheduler_validate_push_times():
    """测试推送时间校验"""
    config = Daily60sPluginConfig()
    config.daily_news.schedule_push = True
    config.daily_news.push_time = "23:30"
    config.gold_price.schedule_push = True
    config.gold_price.push_time = "invalid_time"

    logger = Mock()
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logger,
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    scheduler._validate_push_times()

    # 验证记录了无效时间的错误
    logger.error.assert_called_once()
    assert "push_time 格式非法" in str(logger.error.call_args)


@pytest.mark.asyncio
async def test_scheduler_count_enabled_schedule_tasks():
    """测试统计启用的定时任务数量"""
    config = Daily60sPluginConfig()
    config.daily_news.schedule_push = True
    config.daily_news.enabled = True
    config.gold_price.schedule_push = True
    config.gold_price.enabled = True
    config.ai_news.schedule_push = False
    config.ai_news.enabled = True
    config.gas_price.schedule_push = True
    config.gas_price.enabled = False

    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=ctx,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    # 应该有 2 个启用的定时任务（daily_news 和 gold_price）
    assert scheduler._count_enabled_schedule_tasks() == 2
