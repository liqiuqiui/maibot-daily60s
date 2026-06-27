from plugins.daily60s.core.config import Daily60sPluginConfig
from plugins.daily60s.core.config_resolver import get_command_keywords


def test_daily60s_new_api_config_defaults():
    config = Daily60sPluginConfig()

    assert config.plugin.config_version == "1.0.0"
    assert get_command_keywords(config, "ai_news") == ["/ai_news"]
    assert get_command_keywords(config, "today_in_history") == ["/today_in_history"]
    assert get_command_keywords(config, "it_news") == ["/it_news"]

    assert config.command_trigger_config.trigger_list[0].push_type == "image"


def test_command_trigger_defaults_cover_all_apis():
    config = Daily60sPluginConfig()

    assert [trigger.apis for trigger in config.command_trigger_config.trigger_list] == [
        ["ai_news", "daily_news", "gas_price", "gold_price", "it_news", "today_in_history"],
    ]

    assert all(trigger.enabled for trigger in config.command_trigger_config.trigger_list)


def test_command_alias_adds_extra_keywords_after_default_command():
    config = Daily60sPluginConfig()
    config.command_alias_config.ai_news = ["/ai", "/ai_news"]

    assert get_command_keywords(config, "ai_news") == ["/ai_news", "/ai"]


def test_command_alias_hints_match_default_commands():
    schema = Daily60sPluginConfig.model_json_schema()
    alias_properties = schema["$defs"]["CommandAlias"]["properties"]

    for api_name in ("daily_news", "gold_price", "gas_price", "ai_news", "today_in_history", "it_news"):
        hint = alias_properties[api_name]["hint"]
        assert f"默认 /{api_name}" in hint
