from typing import Any, cast

import pytest

from plugins.daily60s.config import Daily60sPluginConfig
from plugins.daily60s.plugin import Daily60sPlugin


class _FakeSend:
    def __init__(self) -> None:
        self.text_calls: list[tuple[str, str]] = []

    async def text(self, text: str, stream_id: str) -> bool:
        self.text_calls.append((text, stream_id))
        return True


class _FakeLogger:
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


def _attach_fake_context(plugin: Daily60sPlugin) -> _FakeContext:
    fake_context = _FakeContext()
    cast(Any, plugin)._ctx = fake_context
    return fake_context


@pytest.mark.asyncio
async def test_handle_message_missing_additional_config_does_not_crash():
    plugin = Daily60sPlugin()
    plugin.set_plugin_config(Daily60sPluginConfig().model_dump())

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
    config.gas_price.enabled = False
    plugin.set_plugin_config(config.model_dump())
    fake_context = _attach_fake_context(plugin)

    result = await plugin.handle_menu(stream_id="stream-123")

    assert result == (True, "菜单已发送", True)
    assert len(fake_context.send.text_calls) == 1
    menu_text, stream_id = fake_context.send.text_calls[0]
    assert stream_id == "stream-123"
    assert "每日速读菜单" in menu_text
    assert "/60s" in menu_text
    assert "/ai_news [YYYY-MM-DD] [all]" in menu_text
    assert "/gas_price" not in menu_text
    assert "/help" in menu_text
    assert "/帮助" in menu_text


def test_daily60s_menu_is_registered_as_command_component():
    plugin = Daily60sPlugin()

    command_component = next(
        component for component in plugin.get_components() if component["name"] == "daily60s_menu"
    )

    assert command_component["type"] == "COMMAND"
    assert command_component["metadata"]["command_pattern"] == r"^/(menu|help|菜单|帮助)$"


@pytest.mark.asyncio
async def test_handle_menu_command_respects_plugin_enabled_switch():
    plugin = Daily60sPlugin()
    config = Daily60sPluginConfig()
    config.plugin.enabled = False
    plugin.set_plugin_config(config.model_dump())
    fake_context = _attach_fake_context(plugin)

    result = await plugin.handle_menu(stream_id="stream-123")

    assert result == (False, "每日速读插件未启用", False)
    assert fake_context.send.text_calls == []
