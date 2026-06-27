import logging
from datetime import datetime
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import asyncio
import pytest
from maibot_sdk.context import PluginContext

from plugins.daily60s.core.config import Daily60sPluginConfig, ScheduleConfig
from plugins.daily60s.core.fetcher import Fetcher, FetchResult
from plugins.daily60s.core.config_resolver import ScheduleTask, iter_schedule_tasks
from plugins.daily60s.core.scheduler import Scheduler, _normalize_time


class DummyFetcher(Fetcher):
    def __init__(self, result: FetchResult) -> None:
        self.result = result

    async def fetch(
        self,
        api_name: str,
        base_urls: list[str],
        params: dict[str, str] | None = None,
        push_format: str = "text",
    ) -> FetchResult:
        del api_name, base_urls, params, push_format
        return self.result


class FailingFetcher(Fetcher):
    def __init__(self) -> None:
        pass

    async def fetch(
        self,
        api_name: str,
        base_urls: list[str],
        params: dict[str, str] | None = None,
        push_format: str = "text",
    ) -> FetchResult:
        del api_name, base_urls, params, push_format
        raise RuntimeError("fetch failed")


class BlockingFetcher(Fetcher):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def fetch(
        self,
        api_name: str,
        base_urls: list[str],
        params: dict[str, str] | None = None,
        push_format: str = "text",
    ) -> FetchResult:
        del api_name, base_urls, params, push_format
        self.started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return FetchResult(content="hello")


class _FakeChat:
    def __init__(self, should_fail: bool) -> None:
        if should_fail:
            self.get_stream_by_group_id: Any = AsyncMock(side_effect=RuntimeError("get stream failed"))
            self.get_stream_by_user_id: Any = AsyncMock(side_effect=RuntimeError("get stream failed"))
            self.get_group_streams: Any = AsyncMock(side_effect=RuntimeError("get group streams failed"))
            self.get_private_streams: Any = AsyncMock(side_effect=RuntimeError("get private streams failed"))
        else:
            self.get_stream_by_group_id = AsyncMock(
                side_effect=lambda group_id: {"stream_id": f"group_{group_id}"}
            )
            self.get_stream_by_user_id = AsyncMock(
                side_effect=lambda user_id: {"stream_id": f"user_{user_id}"}
            )
            self.get_group_streams = AsyncMock(
                return_value=[
                    {"group_id": "10001", "stream_id": "group_10001"},
                    {"group_info": {"group_id": "10002"}, "stream_id": "group_10002"},
                ]
            )
            self.get_private_streams = AsyncMock(
                return_value=[
                    {"user_id": "20001", "stream_id": "user_20001"},
                    {"user_info": {"user_id": "20002"}, "stream_id": "user_20002"},
                ]
            )


class _FakeSend:
    def __init__(self, should_fail: bool) -> None:
        if should_fail:
            self.text: Any = AsyncMock(side_effect=RuntimeError("send text failed"))
            self.image: Any = AsyncMock(side_effect=RuntimeError("send image failed"))
        else:
            self.text = AsyncMock(return_value=True)
            self.image = AsyncMock(return_value=True)


class _FakeContext:
    def __init__(self, should_fail: bool = False) -> None:
        self.logger = logging.getLogger("daily60s-test-ctx")
        self.chat = _FakeChat(should_fail)
        self.send = _FakeSend(should_fail)


def create_mock_ctx(should_fail: bool = False) -> _FakeContext:
    """创建模拟的 PluginContext"""
    return _FakeContext(should_fail)


def as_plugin_context(ctx: _FakeContext) -> PluginContext:
    return cast(PluginContext, ctx)


def as_logger(logger: Mock) -> logging.Logger:
    return cast(logging.Logger, logger)


def make_schedule_task(
    *,
    api_name: str = "daily_news",
    groups: tuple[str, ...] = (),
    users: tuple[str, ...] = (),
    push_type: str = "text",
    push_time: str = "08:00",
) -> ScheduleTask:
    return ScheduleTask(
        api_name=api_name,
        groups=groups,
        groups_type="whitelist",
        users=users,
        users_type="whitelist",
        push_type=push_type,
        push_time=push_time,
    )


def make_config_with_schedule(*schedule_configs: ScheduleConfig) -> Daily60sPluginConfig:
    config = Daily60sPluginConfig()
    config.schedule_push_config.schedule_list = list(schedule_configs)
    return config


async def do_push(scheduler: Scheduler, task: ScheduleTask) -> None:
    await cast(Any, scheduler)._do_push(task)


def validate_push_times(scheduler: Scheduler) -> None:
    cast(Any, scheduler)._validate_push_times()


def count_enabled_schedule_tasks(scheduler: Scheduler) -> int:
    return cast(Any, scheduler)._count_enabled_schedule_tasks()


def last_push_date(scheduler: Scheduler, task: ScheduleTask) -> str | None:
    task_key = cast(Any, scheduler)._build_task_key(task)
    return cast(Any, scheduler)._last_push_date.get(task_key)


def is_pushing(scheduler: Scheduler, task: ScheduleTask) -> bool:
    task_key = cast(Any, scheduler)._build_task_key(task)
    return bool(cast(Any, scheduler)._pushing.get(task_key, False))


def set_pushing(scheduler: Scheduler, task: ScheduleTask, pushing: bool) -> None:
    task_key = cast(Any, scheduler)._build_task_key(task)
    cast(Any, scheduler)._pushing[task_key] = pushing


def active_push_tasks(scheduler: Scheduler) -> set[asyncio.Task[None]]:
    return cast(set[asyncio.Task[None]], cast(Any, scheduler)._push_tasks)


def schedule_push_task(scheduler: Scheduler, task: ScheduleTask) -> bool:
    return bool(cast(Any, scheduler)._schedule_push_task(task))


@pytest.mark.asyncio
async def test_scheduler_marks_last_push_date_after_successful_push():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    ctx.send.text.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_does_not_mark_last_push_date_when_delivery_fails():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx(should_fail=True)
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_does_not_mark_last_push_date_when_stream_missing():
    task = make_schedule_task(groups=("missing-group",))
    ctx = create_mock_ctx()
    ctx.chat.get_stream_by_group_id = AsyncMock(return_value=None)
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) is None
    ctx.send.text.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_blacklist_schedule_pushes_to_all_except_listed_targets():
    config = make_config_with_schedule(
        ScheduleConfig(
            apis=["daily_news"],
            groups_type="blacklist",
            groups=["10002"],
            users_type="blacklist",
            users=["20002"],
        )
    )
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, iter_schedule_tasks(config)[0])

    ctx.send.text.assert_any_call(text="hello", stream_id="group_10001")
    ctx.send.text.assert_any_call(text="hello", stream_id="user_20001")
    assert ctx.send.text.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_start_logs_enabled_schedule_count():
    config = make_config_with_schedule(
        ScheduleConfig(apis=["daily_news", "gold_price"], groups=["10001"]),
        ScheduleConfig(apis=["ai_news"], enabled=False, groups=["10001"]),
    )
    logger = Mock()
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    scheduler.start()
    await scheduler.stop()

    logger.info.assert_any_call("定时推送调度器已启动，当前启用 %d 条定时任务", 2)


@pytest.mark.asyncio
async def test_scheduler_do_push_with_empty_groups_and_users():
    task = make_schedule_task()
    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    logger.info.assert_any_call("API '%s' 的推送群聊和私聊目标均为空，跳过定时推送", "daily_news")
    ctx.send.text.assert_not_called()
    ctx.send.image.assert_not_called()
    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_do_push_skips_when_plugin_disabled():
    task = make_schedule_task(groups=("10001",))
    config = Daily60sPluginConfig()
    config.plugin.enabled = False
    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    logger.info.assert_any_call("每日信息速递已禁用，跳过定时推送")
    ctx.send.text.assert_not_called()
    ctx.send.image.assert_not_called()
    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_do_push_with_fetch_failure():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=FailingFetcher(),
    )

    await do_push(scheduler, task)

    logger.exception.assert_called_once()
    ctx.send.text.assert_not_called()
    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_do_push_with_image_result():
    task = make_schedule_task(groups=("10001",), push_type="image")
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="image_data", is_image=True)),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    ctx.send.image.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_do_push_to_multiple_groups():
    task = make_schedule_task(groups=("10001", "10002", "10003"))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    assert ctx.send.text.call_count == 3


@pytest.mark.asyncio
async def test_scheduler_do_push_to_multiple_users():
    task = make_schedule_task(users=("20001", "20002"))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    assert ctx.send.text.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_do_push_to_groups_and_users():
    task = make_schedule_task(groups=("10001",), users=("20001",))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    assert ctx.send.text.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_do_push_partial_failure():
    task = make_schedule_task(groups=("10001", "10002"))
    call_count = 0

    async def mock_send_text(*args, **kwargs):
        del args, kwargs
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("send failed")
        return True

    ctx = create_mock_ctx()
    cast(Any, ctx.send).text = mock_send_text
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_scheduler_validate_push_times():
    config = make_config_with_schedule(ScheduleConfig(apis=["daily_news"], push_time="23:30", groups=["10001"]))
    logger = Mock()
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    validate_push_times(scheduler)

    logger.error.assert_not_called()


def test_schedule_config_rejects_invalid_push_time():
    with pytest.raises(ValueError, match="push_time 必须是 HH:MM 格式"):
        ScheduleConfig(apis=["gold_price"], push_time="invalid_time", groups=["10001"])


@pytest.mark.asyncio
async def test_scheduler_count_enabled_schedule_tasks():
    config = make_config_with_schedule(
        ScheduleConfig(apis=["daily_news", "gold_price"], groups=["10001"]),
        ScheduleConfig(apis=["ai_news"], enabled=False, groups=["10001"]),
        ScheduleConfig(apis=["gas_price"], groups=["10001"]),
    )
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=config,
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    assert count_enabled_schedule_tasks(scheduler) == 3


@pytest.mark.asyncio
async def test_scheduler_push_state_prevents_duplicate_push():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    logger = Mock()
    scheduler = Scheduler(
        logger=as_logger(logger),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    set_pushing(scheduler, task, True)
    await do_push(scheduler, task)

    logger.debug.assert_any_call("API '%s' 正在推送中，跳过本次推送", "daily_news")
    ctx.send.text.assert_not_called()
    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_schedule_push_task_marks_pushing_before_task_runs():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=BlockingFetcher(),
    )

    scheduled = schedule_push_task(scheduler, task)
    duplicate_scheduled = schedule_push_task(scheduler, task)

    assert scheduled is True
    assert duplicate_scheduled is False
    assert is_pushing(scheduler, task) is True
    assert len(active_push_tasks(scheduler)) == 1

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_active_push_tasks():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    fetcher = BlockingFetcher()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=fetcher,
    )

    assert schedule_push_task(scheduler, task) is True
    await fetcher.started.wait()

    await scheduler.stop()

    assert fetcher.cancelled is True
    assert active_push_tasks(scheduler) == set()
    assert is_pushing(scheduler, task) is False


@pytest.mark.asyncio
async def test_scheduler_push_state_cleared_after_push():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    assert is_pushing(scheduler, task) is False
    await do_push(scheduler, task)

    assert is_pushing(scheduler, task) is False
    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_scheduler_push_state_cleared_on_failure():
    task = make_schedule_task(groups=("10001",))
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=FailingFetcher(),
    )

    await do_push(scheduler, task)

    assert is_pushing(scheduler, task) is False
    assert last_push_date(scheduler, task) is None


@pytest.mark.asyncio
async def test_scheduler_triggers_push_when_time_exceeded():
    task = make_schedule_task(groups=("10001",), push_time="08:00")
    ctx = create_mock_ctx()
    scheduler = Scheduler(
        logger=logging.getLogger("daily60s-test"),
        ctx=as_plugin_context(ctx),
        config=Daily60sPluginConfig(),
        fetcher=DummyFetcher(FetchResult(content="hello")),
    )

    assert last_push_date(scheduler, task) is None
    await do_push(scheduler, task)

    assert last_push_date(scheduler, task) == datetime.now().strftime("%Y-%m-%d")
    ctx.send.text.assert_called_once()


def test_normalize_time_standard_format():
    """测试规范化标准格式的时间"""
    assert _normalize_time("08:00") == "08:00"
    assert _normalize_time("23:59") == "23:59"
    assert _normalize_time("00:00") == "00:00"


def test_normalize_time_non_standard_format():
    """测试规范化非标准格式的时间"""
    assert _normalize_time("8:00") == "08:00"
    assert _normalize_time("9:30") == "09:30"
    assert _normalize_time("0:00") == "00:00"


def test_normalize_time_invalid_format():
    """测试规范化无效格式"""
    assert _normalize_time("invalid") == "invalid"
    assert _normalize_time("25:00") == "25:00"
    assert _normalize_time("12:60") == "12:60"
