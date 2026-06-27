import logging

import pytest

import plugins.daily60s.core.api_registry as api_registry_module
import plugins.daily60s.core.fetcher as fetcher_module


def test_api_registry_does_not_define_unused_default_config_fields():
    for definition in api_registry_module.API_REGISTRY.values():
        assert not hasattr(definition, "default_keywords")
        assert not hasattr(definition, "default_push_format")
        assert not hasattr(definition, "default_schedule_push")


@pytest.mark.parametrize(
    ("api_name", "arg_tokens", "expected_params"),
    [
        ("ai_news", [], {}),
        ("ai_news", ["all"], {"all": "1"}),
        ("today_in_history", [], {}),
        ("today_in_history", ["2025-06-18"], {"date": "2025-06-18"}),
        ("it_news", [], {}),
        ("it_news", ["12"], {"limit": "12"}),
        ("gas_price", ["北京"], {"region": "北京"}),
    ],
)
def test_build_api_request_params(api_name, arg_tokens, expected_params):
    definition = api_registry_module.API_REGISTRY[api_name]

    helper = getattr(api_registry_module, "build_api_request_params", None)
    assert callable(helper)
    assert helper(definition, arg_tokens) == expected_params


@pytest.mark.parametrize(
    ("api_name", "arg_tokens"),
    [
        ("ai_news", ["oops"]),
        ("today_in_history", ["2025/06/18"]),
        ("today_in_history", ["2025-06-18", "extra"]),
        ("it_news", ["0"]),
        ("it_news", ["51"]),
        ("gas_price", []),
    ],
)
def test_build_api_request_params_invalid(api_name, arg_tokens):
    definition = api_registry_module.API_REGISTRY[api_name]
    helper = getattr(api_registry_module, "build_api_request_params", None)
    assert callable(helper)

    with pytest.raises(api_registry_module.CommandUsageError):
        helper(definition, arg_tokens)


def test_renderers_module_builds_ai_news_html_with_dynamic_count():
    import plugins.daily60s.core.renderers as renderers_module

    html = renderers_module.build_ai_news_html(
        date_text="2026-06-18",
        source_text="数据来源：60s API / AI 工具集等公开来源",
        items=[
            {
                "title": "第一条 AI 资讯",
                "source": "来源 A",
                "date": "2026-06-18",
                "detail": "这里是第一条摘要",
            },
            {
                "title": "第二条 AI 资讯",
                "source": "来源 B",
                "date": "2026-06-18",
                "detail": "这里是第二条摘要",
            },
        ],
    )

    assert "news-count" in html
    assert "共 2 条" in html
    assert "ai-item" in html

    empty_html = renderers_module.build_ai_news_html(
        date_text="2026-06-18",
        source_text="数据来源：60s API / AI 工具集等公开来源",
        items=[],
    )
    assert "ai-empty" in empty_html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_name", "payload", "text_needles"),
    [
        (
            "gold_price",
            {
                "data": {
                    "date": "2026-06-18",
                    "metals": [
                        {
                            "name": "黄金",
                            "today_price": "768.50",
                            "sell_price": "770.00",
                            "high_price": "772.00",
                            "low_price": "765.00",
                            "unit": "元/克",
                            "updated": "2026-06-18 09:12:00",
                        }
                    ],
                }
            },
            ["黄金价格", "黄金", "768.50"],
        ),
        (
            "ai_news",
            {
                "data": {
                    "date": "2026-06-18",
                    "news": [
                        {
                            "title": "OpenAI 发布新能力",
                            "source": "Viki",
                            "date": "2026-06-18 08:00:00",
                            "link": "https://example.com/ai-1",
                        }
                    ],
                }
            },
            ["AI", "OpenAI 发布新能力", "Viki"],
        ),
        (
            "today_in_history",
            {
                "data": {
                    "date": "6-18",
                    "month": 6,
                    "day": 18,
                    "items": [
                        {
                            "title": "某个历史事件",
                            "year": "1980",
                            "description": "这里是简述",
                            "event_type": "event",
                            "link": "https://example.com/history-1",
                        }
                    ],
                }
            },
            ["历史上的今天", "1980", "某个历史事件"],
        ),
        (
            "it_news",
            {
                "data": [
                    {
                        "title": "某条 IT 资讯",
                        "description": "这里是摘要",
                        "created": "2026-06-18 09:30:00",
                        "created_at": "2026-06-18T09:30:00+08:00",
                        "link": "https://example.com/it-1",
                    }
                ]
            },
            ["IT", "某条 IT 资讯", "这里是摘要"],
        ),
    ],
)
async def test_new_api_formatter_supports_text_and_image(api_name, payload, text_needles):
    fetcher = fetcher_module.Fetcher(logger=logging.getLogger("daily60s-test"), timeout=5)
    definition = api_registry_module.API_REGISTRY[api_name]

    text_result = await fetcher._format(payload, definition, push_format="text")
    image_result = await fetcher._format(payload, definition, push_format="image")

    assert not text_result.is_image
    for needle in text_needles:
        assert needle in text_result.content

    assert image_result.is_image
    assert image_result.content == ""
    assert "<html" in image_result.html.lower()

    if api_name == "gold_price":
        assert "gold-card" in image_result.html
        assert "price-figure" in image_result.html
    elif api_name == "ai_news":
        assert "ai-grid" in image_result.html
        assert "neural-halo" in image_result.html
        assert "example.com" not in image_result.html
    elif api_name == "today_in_history":
        assert "history-card" in image_result.html
        assert "history-year" in image_result.html
        assert "paper-grain" in image_result.html
        assert "archive-seal" in image_result.html
        assert "example.com/history-1" not in image_result.html
    elif api_name == "it_news":
        assert "example.com" not in image_result.html


@pytest.mark.asyncio
async def test_gas_price_formatter_rejects_invalid_structure():
    fetcher = fetcher_module.Fetcher(logger=logging.getLogger("daily60s-test"), timeout=5)

    with pytest.raises(RuntimeError):
        await fetcher._format_gas_price({"code": 200, "data": []}, push_format="text")


@pytest.mark.asyncio
async def test_gas_price_formatter_image_uses_market_card_layout():
    fetcher = fetcher_module.Fetcher(logger=logging.getLogger("daily60s-test"), timeout=5)
    payload = {
        "code": 200,
        "data": {
            "region": "北京",
            "updated": "2026-06-18 09:30:00",
            "trend": {"description": "今晚 24 时预计上调 0.12 元/升"},
            "items": [
                {"name": "92号汽油", "price": 7.32},
                {"name": "95号汽油", "price": 7.81},
            ],
        },
    }

    image_result = await fetcher._format_gas_price(payload, push_format="image")

    assert image_result.is_image
    assert "fuel-card" in image_result.html
    assert "fuel-price" in image_result.html
