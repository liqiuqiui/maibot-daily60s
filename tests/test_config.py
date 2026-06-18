from plugins.daily60s.config import Daily60sPluginConfig


def test_daily60s_new_api_config_defaults():
    config = Daily60sPluginConfig()

    assert [api.name for api in config.apis] == [
        "daily_news",
        "gold_price",
        "gas_price",
        "ai_news",
        "today_in_history",
        "it_news",
    ]

    assert config.ai_news.keywords == ["/ai_news", "/ai"]
    assert config.ai_news.push_format == "image"

    assert config.today_in_history.keywords == ["/today_history", "/history_today"]
    assert config.today_in_history.push_format == "image"

    assert config.it_news.keywords == ["/it_news", "/it"]
    assert config.it_news.push_format == "image"

    assert config.gold_price.push_format == "image"
