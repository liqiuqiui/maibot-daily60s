import logging
from datetime import datetime
from unittest.mock import Mock

import pytest

from plugins.daily60s.config import Daily60sPluginConfig
from plugins.daily60s.fetcher import FetchResult
from plugins.daily60s.scheduler import Scheduler


class DummyFetcher:
    def __init__(self, result: FetchResult):
        self.result = result

    async def fetch(self, **kwargs):
        return self.result


class DummySender:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent_messages = []

    async def send_group(self, group_id: int, message: str) -> None:
        if self.should_fail:
            raise RuntimeError("send group failed")
        self.sent_messages.append(("group", group_id, message))

    async def send_group_image(self, group_id: int, image_b64: str) -> None:
        if self.should_fail:
            raise RuntimeError("send group image failed")
        self.sent_messages.append(("group_image", group_id, image_b64))

    async def send_user(self, user_id: int, message: str) -> None:
        if self.should_fail:
            raise RuntimeError("send user failed")
        self.sent_messages.append(("user", user_id, message))

    async def send_user_image(self, user_id: int, image_b64: str) -> None:
        if self.should_fail:
            raise RuntimeError("send user image failed")
        self.sent_messages.append(("user_image", user_id, image_b64))


@pytest.mark.asyncio
async def test_scheduler_marks_last_push_date_after_successful_push():
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]

    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
        sender=DummySender(),
    )

    await scheduler._do_push(config.daily_news)

    assert scheduler._last_push_date["daily_news"] == datetime.now().strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_scheduler_does_not_mark_last_push_date_when_delivery_fails():
    config = Daily60sPluginConfig()
    config.daily_news.push_groups = ["10001"]

    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
        sender=DummySender(should_fail=True),
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
    scheduler = Scheduler(
        logger=logger,
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
        sender=DummySender(),
    )

    scheduler.start()
    await scheduler.stop()

    logger.info.assert_any_call("定时推送调度器已启动，当前启用 %d 条定时任务", 2)
