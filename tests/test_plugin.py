import pytest

from plugins.daily60s.config import Daily60sPluginConfig
from plugins.daily60s.plugin import Daily60sPlugin


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
