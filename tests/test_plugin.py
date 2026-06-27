from typing import Any, cast

import pytest

from plugins.daily60s.core.config import Daily60sPluginConfig, TriggerConfig
from plugins.daily60s.core.plugin import Daily60sPlugin


class _FakeSend:
    def __init__(self) -> None:
        self.text_calls: list[tuple[str, str]] = []

    async def text(self, text: str, stream_id: str) -> bool:
        self.text_calls.append((text, stream_id))
        return True


class _FakeLogger:
    def debug(self, *args, **kwargs) -> None:
        pass

    def warning(self, *args, **kwargs) -> None:
        pass

    def info(self, *args, **kwargs) -> None:
        pass

    def error(self, *args, **kwargs) -> None:
        pass

    def exception(self, *args, **kwargs) -> None:
        pass


class _FakeContext:
    def __init__(self) -> None:
        self.send = _FakeSend()
        self.logger = _FakeLogger()
        self.chat = None


def _attach_fake_context(plugin: Daily60sPlugin) -> _FakeContext:
    fake_context = _FakeContext()
    cast(Any, plugin)._ctx = fake_context
    return fake_context


def _set_config(plugin: Daily60sPlugin, config: Daily60sPluginConfig) -> None:
    cast(Any, plugin)._plugin_config_data = config.model_dump()
    cast(Any, plugin)._plugin_config_instance = config


@pytest.mark.asyncio
async def test_handle_message_missing_additional_config_does_not_crash():
    plugin = Daily60sPlugin()
    _set_config(plugin, Daily60sPluginConfig())

    result = await plugin.handle_message(
        message={
            "is_command": True,
            "processed_plain_text": "/60s",
            "message_info": {},
        }
    )

    assert result is None


@pytest.mark.asyncio
async def test_handle_menu_command_sends_enabled_api_menu():
    plugin = Daily60sPlugin()
    config = Daily60sPluginConfig()
    config.command_trigger_config.trigger_list = [
        TriggerConfig(apis=["daily_news", "ai_news"]),
    ]
    config.command_alias_config.daily_news = ["/60s"]
    config.command_alias_config.ai_news = ["/ai"]
    _set_config(plugin, config)
    fake_context = _attach_fake_context(plugin)

    result = await plugin.handle_menu(stream_id="stream-123")

    assert result == (True, "菜单已发送", True)
    assert len(fake_context.send.text_calls) == 1
    menu_text, stream_id = fake_context.send.text_calls[0]
    assert stream_id == "stream-123"
    assert "每日信息速递菜单" in menu_text
    assert "每日新闻" in menu_text
    assert "/daily_news" in menu_text
    assert "获取每日 60 秒新闻简报" in menu_text
    assert "别名：/60s" in menu_text
    assert "AI 资讯快报" in menu_text
    assert "/ai_news [YYYY-MM-DD] [all]" in menu_text
    assert "获取 AI 行业资讯快报" in menu_text
    assert "别名：/ai" in menu_text
    assert "/gas_price" not in menu_text
    assert "/help" in menu_text
    assert "/帮助" in menu_text


def test_daily60s_menu_is_registered_as_command_component():
    plugin = Daily60sPlugin()

    command_component = next(component for component in plugin.get_components() if component["name"] == "menu")

    assert command_component["type"] == "COMMAND"
    assert command_component["metadata"]["command_pattern"] == r"^/(menu|help|菜单|帮助)$"


@pytest.mark.asyncio
async def test_on_load_starts_scheduler(monkeypatch: pytest.MonkeyPatch):
    started = False

    class _FakeScheduler:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def start(self) -> None:
            nonlocal started
            started = True

    monkeypatch.setattr("plugins.daily60s.core.plugin.Scheduler", _FakeScheduler)

    plugin = Daily60sPlugin()
    _set_config(plugin, Daily60sPluginConfig())
    fake_context = _attach_fake_context(plugin)

    await plugin.on_load()

    assert started is True
    assert cast(Any, plugin)._scheduler is not None
    assert cast(Any, plugin)._scheduler.kwargs["ctx"] is fake_context


@pytest.mark.asyncio
async def test_on_load_does_not_start_scheduler_when_plugin_disabled(monkeypatch: pytest.MonkeyPatch):
    started = False

    class _FakeScheduler:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def start(self) -> None:
            nonlocal started
            started = True

    monkeypatch.setattr("plugins.daily60s.core.plugin.Scheduler", _FakeScheduler)

    plugin = Daily60sPlugin()
    config = Daily60sPluginConfig()
    config.plugin.enabled = False
    _set_config(plugin, config)
    _attach_fake_context(plugin)

    await plugin.on_load()

    assert started is False
    assert cast(Any, plugin)._scheduler is None


@pytest.mark.asyncio
async def test_handle_menu_command_respects_plugin_enabled_switch():
    plugin = Daily60sPlugin()
    config = Daily60sPluginConfig()
    config.plugin.enabled = False
    _set_config(plugin, config)
    fake_context = _attach_fake_context(plugin)

    result = await plugin.handle_menu(stream_id="stream-123")

    assert result == (False, "每日信息速递未启用", False)
    assert fake_context.send.text_calls == []


@pytest.mark.asyncio
async def test_handle_message_sends_usage_to_resolved_stream_id(monkeypatch: pytest.MonkeyPatch):
    class _FakeChat:
        async def get_stream_by_group_id(self, group_id: str):
            assert group_id == "10001"
            return {"stream_id": "stream-group-10001"}

        async def get_stream_by_user_id(self, user_id: str):
            raise AssertionError(f"不应该查询私聊流：{user_id}")

    plugin = Daily60sPlugin()
    config = Daily60sPluginConfig()
    config.command_trigger_config.trigger_list = [TriggerConfig(apis=["gas_price"])]
    _set_config(plugin, config)
    fake_context = _attach_fake_context(plugin)
    fake_context.chat = _FakeChat()
    cast(Any, plugin)._fetcher = object()

    result = await plugin.handle_message(
        message={
            "is_command": True,
            "processed_plain_text": "/gas_price",
            "message_info": {
                "additional_config": {"napcat_message_type": "group"},
                "group_info": {"group_id": "10001"},
            },
        }
    )

    assert result == {"action": "abort"}
    assert fake_context.send.text_calls == [("参数错误，用法：/gas_price <region>", "stream-group-10001")]
