"""每日信息速递插件 - 图片长图渲染函数。"""

from __future__ import annotations

from typing import Any

import html


def build_gas_price_html(region: str, items: list[dict[str, Any]], trend: dict[str, Any], updated: str) -> str:
    """构建油价卡片 HTML。"""

    description = str(trend.get("description") or "")
    cards_html = "\n".join(
        f"""
        <section class="fuel-card">
            <div class="fuel-card-top">
                <div class="fuel-name">{html.escape(item["name"])}</div>
                <div class="fuel-unit">元/升</div>
            </div>
            <div class="fuel-price-wrap">
                <div class="fuel-price-label">当前价格</div>
                <div class="fuel-price">{item["price"]:.2f}</div>
            </div>
        </section>"""
        for item in items
    )
    tip_html = f'<div class="trend-tip">趋势提示  {html.escape(description)}</div>' if description else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: 760px;
                padding: 28px;
                background:
                    radial-gradient(circle at top right, rgba(104, 180, 255, 0.18), transparent 34%),
                    linear-gradient(180deg, #eef5ff 0%, #edf2f8 40%, #e8edf4 100%);
                color: #1f2937;
                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            }}
            .board {{
                overflow: hidden;
                border: 1px solid rgba(66, 106, 157, 0.18);
                border-radius: 24px;
                background: rgba(255, 255, 255, 0.94);
                box-shadow: 0 18px 44px rgba(44, 82, 130, 0.12);
            }}
            .hero {{
                position: relative;
                padding: 30px 30px 24px;
                background:
                    linear-gradient(135deg, #13243f 0%, #1f4a7d 48%, #4f8dd8 100%);
                color: #eef6ff;
            }}
            .hero::after {{
                content: "";
                position: absolute;
                inset: auto -40px -90px auto;
                width: 240px;
                height: 240px;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(170, 219, 255, 0.34) 0%, rgba(170, 219, 255, 0) 72%);
            }}
            .hero-kicker {{
                position: relative;
                z-index: 1;
                font-size: 12px;
                color: rgba(230, 242, 255, 0.72);
            }}
            .hero-title {{
                position: relative;
                z-index: 1;
                margin-top: 8px;
                font-size: 34px;
                line-height: 1.16;
                font-weight: 700;
            }}
            .hero-meta {{
                position: relative;
                z-index: 1;
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 16px;
            }}
            .hero-chip {{
                padding: 8px 12px;
                border: 1px solid rgba(225, 239, 255, 0.18);
                border-radius: 999px;
                background: rgba(245, 250, 255, 0.1);
                font-size: 13px;
                color: rgba(239, 247, 255, 0.9);
            }}
            .content {{
                padding: 22px;
            }}
            .fuel-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 14px;
            }}
            .fuel-card {{
                padding: 18px;
                border: 1px solid rgba(123, 151, 194, 0.24);
                border-radius: 18px;
                background:
                    linear-gradient(180deg, rgba(250, 252, 255, 0.98) 0%, rgba(239, 246, 255, 0.94) 100%);
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
            }}
            .fuel-card-top {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
            }}
            .fuel-name {{
                font-size: 20px;
                font-weight: 700;
                color: #17355b;
            }}
            .fuel-unit {{
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(71, 117, 182, 0.08);
                color: #4f6e99;
                font-size: 12px;
            }}
            .fuel-price-wrap {{
                margin-top: 18px;
            }}
            .fuel-price-label {{
                font-size: 13px;
                color: #6982a6;
            }}
            .fuel-price {{
                margin-top: 8px;
                font-size: 42px;
                line-height: 1;
                font-weight: 800;
                color: #1d5fa8;
                font-variant-numeric: tabular-nums;
            }}
            .trend-tip {{
                margin-top: 16px;
                padding: 14px 16px;
                border-radius: 16px;
                background: linear-gradient(180deg, rgba(227, 239, 255, 0.86) 0%, rgba(241, 247, 255, 0.92) 100%);
                border: 1px solid rgba(131, 165, 211, 0.26);
                font-size: 13px;
                line-height: 1.7;
                color: #46617f;
            }}
        </style>
    </head>
    <body>
        <main class="board">
            <header class="hero">
                <div class="hero-kicker">地区油价播报</div>
                <div class="hero-title">{html.escape(region)}今日油价</div>
                <div class="hero-meta">
                    <div class="hero-chip">更新时间 {html.escape(updated)}</div>
                    <div class="hero-chip">数据来源 60s API</div>
                </div>
            </header>
            <section class="content">
                <div class="fuel-grid">
                    {cards_html}
                </div>
                {tip_html}
            </section>
        </main>
    </body>
</html>
"""


def build_gold_price_html(date_value: str, metals: list[dict[str, str]]) -> str:
    """构建黄金价格长图 HTML。"""

    cards_html = "\n".join(
        f"""
        <section class="gold-card">
            <div class="gold-card-top">
                <div class="metal-name">{html.escape(metal["name"])}</div>
                <div class="unit-pill">{html.escape(metal["unit"])}</div>
            </div>
            <div class="price-main">
                <div class="price-label">今日价格</div>
                <div class="price-figure">{html.escape(metal["today"] or "--")}</div>
            </div>
            <div class="price-grid">
                <div class="metric">
                    <div class="metric-label">卖出价</div>
                    <div class="metric-value">{html.escape(metal["sell"] or "--")}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">最高价</div>
                    <div class="metric-value">{html.escape(metal["high"] or "--")}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">最低价</div>
                    <div class="metric-value">{html.escape(metal["low"] or "--")}</div>
                </div>
            </div>
            <div class="update-line">更新时间 {html.escape(metal["updated"] or "--")}</div>
        </section>
        """
        for metal in metals
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                width: 760px;
                padding: 28px;
                background:
                    radial-gradient(circle at top left, rgba(255, 222, 156, 0.28), transparent 34%),
                    linear-gradient(180deg, #f7f1e3 0%, #f2f4f8 34%, #edf1f7 100%);
                color: #1d2433;
                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            }}
            .board {{
                overflow: hidden;
                border: 1px solid rgba(155, 121, 55, 0.18);
                border-radius: 24px;
                background: rgba(255, 255, 255, 0.92);
                box-shadow: 0 18px 50px rgba(76, 62, 31, 0.12);
            }}
            .hero {{
                position: relative;
                padding: 30px 30px 24px;
                background:
                    linear-gradient(135deg, #20180d 0%, #4b3a1f 42%, #92703a 100%);
                color: #fff7e6;
            }}
            .hero::after {{
                content: "";
                position: absolute;
                inset: auto -60px -80px auto;
                width: 220px;
                height: 220px;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(255, 228, 168, 0.34) 0%, rgba(255, 228, 168, 0) 72%);
            }}
            .eyebrow {{
                position: relative;
                z-index: 1;
                font-size: 12px;
                letter-spacing: 0;
                color: rgba(255, 244, 214, 0.76);
            }}
            .hero-title {{
                position: relative;
                z-index: 1;
                margin-top: 8px;
                font-size: 34px;
                line-height: 1.16;
                font-weight: 700;
            }}
            .hero-meta {{
                position: relative;
                z-index: 1;
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 16px;
            }}
            .hero-chip {{
                padding: 8px 12px;
                border: 1px solid rgba(255, 240, 205, 0.18);
                border-radius: 999px;
                background: rgba(255, 250, 236, 0.08);
                font-size: 13px;
                color: rgba(255, 247, 230, 0.9);
            }}
            .content {{
                padding: 22px;
            }}
            .cards {{
                display: grid;
                gap: 14px;
            }}
            .gold-card {{
                padding: 18px 18px 16px;
                border: 1px solid rgba(199, 166, 101, 0.22);
                border-radius: 18px;
                background:
                    linear-gradient(180deg, rgba(255, 252, 244, 0.96) 0%, rgba(250, 245, 232, 0.92) 100%);
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
            }}
            .gold-card-top {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
            }}
            .metal-name {{
                font-size: 20px;
                font-weight: 700;
                color: #3f2f16;
            }}
            .unit-pill {{
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(132, 95, 26, 0.08);
                color: #7a5b22;
                font-size: 12px;
            }}
            .price-main {{
                display: flex;
                align-items: end;
                justify-content: space-between;
                gap: 12px;
                margin-top: 18px;
            }}
            .price-label {{
                font-size: 13px;
                color: #8a7346;
            }}
            .price-figure {{
                font-size: 42px;
                line-height: 1;
                font-weight: 800;
                color: #b07d21;
                font-variant-numeric: tabular-nums;
            }}
            .price-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
                margin-top: 18px;
            }}
            .metric {{
                padding: 12px 12px 10px;
                border-radius: 14px;
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid rgba(214, 191, 143, 0.3);
            }}
            .metric-label {{
                font-size: 12px;
                color: #8f7a4f;
            }}
            .metric-value {{
                margin-top: 8px;
                font-size: 20px;
                font-weight: 700;
                color: #2d3546;
                font-variant-numeric: tabular-nums;
            }}
            .update-line {{
                margin-top: 14px;
                font-size: 12px;
                color: #8b8f97;
            }}
        </style>
    </head>
    <body>
        <main class="board">
            <header class="hero">
                <div class="eyebrow">60s API 行情快照</div>
                <div class="hero-title">黄金价格</div>
                <div class="hero-meta">
                    <div class="hero-chip">日期 {html.escape(date_value or "--")}</div>
                    <div class="hero-chip">数据来源 60s API</div>
                    <div class="hero-chip">单位 元/克</div>
                </div>
            </header>
            <section class="content">
                <div class="cards">
                    {cards_html}
                </div>
            </section>
        </main>
    </body>
</html>
"""


def build_digest_item_html(title: str, meta: list[str], summary: str) -> str:
    """构建统一资讯条目 HTML。"""

    meta_text = " · ".join(part for part in meta if part)
    summary_text = html.escape(_truncate_text(summary, 160))
    summary_html = f'<div class="summary">{summary_text}</div>' if summary_text else ""
    meta_html = f'<div class="meta">{html.escape(meta_text)}</div>' if meta_text else ""

    return f"""
        <section class="item">
            <div class="item-title">{html.escape(title)}</div>
            {meta_html}
            {summary_html}
        </section>
    """


def build_ai_news_html(date_text: str, source_text: str, items: list[dict[str, str]]) -> str:
    """构建 AI 资讯快报专用长图。"""

    count_text = f"共 {len(items)} 条"
    if items:
        item_blocks = "\n".join(
            f"""
            <section class="ai-item">
                <div class="ai-item-head">
                    <div class="signal-dot"></div>
                    <div class="title-wrap">
                        <div class="ai-item-title">{html.escape(item["title"])}</div>
                        <div class="ai-meta">{html.escape(" · ".join(part for part in [item["source"], item["date"]] if part))}</div>
                    </div>
                </div>
                <div class="circuit-ribbon"></div>
                <div class="ai-summary">{html.escape(_truncate_text(item.get("detail", ""), 160))}</div>
            </section>
            """
            for item in items
        )
    else:
        item_blocks = """
        <section class="ai-empty">
            <div class="ai-empty-title">当前暂无可展示的 AI 快报</div>
            <div class="ai-empty-text">接口返回的资讯条数会随来源实时变化，下一次拉取有内容后会自动按同一版式展开。</div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                width: 760px;
                padding: 28px;
                background:
                    radial-gradient(circle at 12% 0%, rgba(49, 113, 255, 0.24), transparent 24%),
                    radial-gradient(circle at 84% 16%, rgba(0, 221, 255, 0.16), transparent 26%),
                    linear-gradient(180deg, #040b15 0%, #081220 48%, #05101a 100%);
                color: #e6f7ff;
                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            }}
            .board {{
                position: relative;
                overflow: hidden;
                border: 1px solid rgba(84, 142, 255, 0.24);
                border-radius: 30px;
                background:
                    linear-gradient(180deg, rgba(7, 18, 34, 0.98) 0%, rgba(4, 14, 27, 0.98) 100%);
                box-shadow:
                    0 24px 60px rgba(0, 0, 0, 0.36),
                    inset 0 1px 0 rgba(194, 233, 255, 0.08);
            }}
            .ai-grid {{
                position: absolute;
                inset: 0;
                pointer-events: none;
                background:
                    linear-gradient(rgba(87, 136, 255, 0.08) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(87, 136, 255, 0.08) 1px, transparent 1px);
                background-size: 32px 32px;
                mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.8), transparent 86%);
            }}
            .hero {{
                position: relative;
                padding: 34px 32px 26px;
                background:
                    radial-gradient(circle at 16% 20%, rgba(88, 141, 255, 0.28), transparent 34%),
                    linear-gradient(135deg, #0c1830 0%, #12284b 42%, #0f3968 100%);
                border-bottom: 1px solid rgba(95, 148, 255, 0.16);
            }}
            .hero::after {{
                content: "";
                position: absolute;
                inset: auto 130px -34px 34px;
                height: 1px;
                background: linear-gradient(90deg, rgba(53, 218, 255, 0.4) 0%, rgba(95, 123, 255, 0) 100%);
            }}
            .neural-halo {{
                position: absolute;
                right: 26px;
                top: 16px;
                width: 196px;
                height: 196px;
                border-radius: 999px;
                background:
                    radial-gradient(circle, rgba(42, 224, 255, 0.24) 0%, rgba(42, 224, 255, 0.08) 24%, rgba(42, 224, 255, 0) 56%),
                    repeating-radial-gradient(circle, rgba(99, 158, 255, 0.18) 0 2px, rgba(99, 158, 255, 0) 2px 16px);
                opacity: 0.96;
            }}
            .hero-orbit {{
                position: absolute;
                right: 68px;
                top: 70px;
                width: 112px;
                height: 112px;
                border-radius: 999px;
                border: 1px solid rgba(121, 184, 255, 0.18);
                box-shadow:
                    0 0 0 14px rgba(79, 132, 255, 0.06),
                    0 0 0 30px rgba(79, 132, 255, 0.05);
            }}
            .hero-kicker {{
                position: relative;
                z-index: 1;
                font-size: 12px;
                color: rgba(181, 224, 255, 0.72);
            }}
            .hero-title {{
                position: relative;
                z-index: 1;
                margin-top: 10px;
                font-size: 40px;
                line-height: 1.14;
                font-weight: 760;
                color: #f4fbff;
                text-shadow: 0 0 28px rgba(73, 165, 255, 0.16);
            }}
            .hero-subtitle {{
                position: relative;
                z-index: 1;
                max-width: 440px;
                margin-top: 12px;
                font-size: 15px;
                line-height: 1.7;
                color: #a9c6e7;
            }}
            .hero-meta {{
                position: relative;
                z-index: 1;
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 18px;
            }}
            .hero-chip {{
                padding: 8px 12px;
                border: 1px solid rgba(123, 182, 255, 0.22);
                border-radius: 999px;
                background: rgba(10, 24, 46, 0.55);
                backdrop-filter: blur(6px);
                font-size: 13px;
                color: rgba(222, 244, 255, 0.9);
            }}
            .news-count {{
                color: #c9f6ff;
                border-color: rgba(53, 218, 255, 0.3);
                box-shadow: inset 0 0 0 1px rgba(53, 218, 255, 0.08);
            }}
            .content {{
                position: relative;
                padding: 20px 22px 24px;
            }}
            .stack {{
                display: grid;
                gap: 14px;
            }}
            .ai-item {{
                position: relative;
                padding: 18px 18px 16px;
                border: 1px solid rgba(85, 132, 232, 0.24);
                border-radius: 22px;
                background:
                    linear-gradient(180deg, rgba(10, 23, 42, 0.96) 0%, rgba(8, 19, 36, 0.94) 100%);
                box-shadow:
                    inset 0 1px 0 rgba(183, 225, 255, 0.05),
                    0 12px 24px rgba(0, 0, 0, 0.18);
            }}
            .ai-item::before {{
                content: "";
                position: absolute;
                inset: 14px auto 14px 0;
                width: 4px;
                border-radius: 999px;
                background: linear-gradient(180deg, #35dbff 0%, #5f7bff 100%);
                box-shadow: 0 0 12px rgba(53, 219, 255, 0.26);
            }}
            .ai-item-head {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                min-width: 0;
            }}
            .signal-dot {{
                width: 12px;
                height: 12px;
                flex: 0 0 12px;
                margin-top: 8px;
                border-radius: 999px;
                background: #38e1ff;
                box-shadow: 0 0 18px rgba(56, 225, 255, 0.72);
            }}
            .title-wrap {{
                min-width: 0;
                flex: 1;
            }}
            .ai-item-title {{
                min-width: 0;
                font-size: 22px;
                line-height: 1.42;
                font-weight: 700;
                color: #f2fbff;
            }}
            .ai-meta {{
                margin-top: 8px;
                font-size: 13px;
                line-height: 1.5;
                color: #89afd4;
            }}
            .circuit-ribbon {{
                height: 18px;
                margin-top: 12px;
                background:
                    linear-gradient(90deg, rgba(52, 217, 255, 0.22) 0 18%, rgba(52, 217, 255, 0) 18%),
                    repeating-linear-gradient(90deg, rgba(95, 123, 255, 0.18) 0 10px, rgba(95, 123, 255, 0) 10px 24px);
                mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.88), transparent 92%);
                opacity: 0.8;
            }}
            .ai-summary {{
                margin-top: 10px;
                font-size: 15px;
                line-height: 1.78;
                color: #c8d9ec;
                white-space: pre-wrap;
                word-break: break-word;
            }}
            .ai-empty {{
                padding: 28px 24px;
                border: 1px dashed rgba(97, 152, 255, 0.28);
                border-radius: 22px;
                background: rgba(10, 22, 40, 0.72);
            }}
            .ai-empty-title {{
                font-size: 20px;
                font-weight: 700;
                color: #eff9ff;
            }}
            .ai-empty-text {{
                margin-top: 10px;
                font-size: 14px;
                line-height: 1.7;
                color: #9ab8d8;
            }}
        </style>
    </head>
    <body>
        <main class="board">
            <div class="ai-grid"></div>
            <header class="hero">
                <div class="neural-halo"></div>
                <div class="hero-orbit"></div>
                <div class="hero-kicker">智能前沿追踪</div>
                <div class="hero-title">AI 资讯快报</div>
                <div class="hero-subtitle">聚焦模型、工具、算力与生态动态，用更像 AI 简报首页的方式承载每天不固定条数的重点资讯。</div>
                <div class="hero-meta">
                    <div class="hero-chip">日期 {html.escape(date_text or "--")}</div>
                    <div class="hero-chip">{html.escape(source_text)}</div>
                    <div class="hero-chip news-count">{count_text}</div>
                </div>
            </header>
            <section class="content">
                <div class="stack">
                    {item_blocks}
                </div>
            </section>
        </main>
    </body>
</html>
"""


def build_today_in_history_html(date_display: str, items: list[dict[str, str]]) -> str:
    """构建历史上的今天专用时间轴长图。"""

    cards_html = "\n".join(
        f"""
        <section class="history-card">
            <div class="history-mark">
                <div class="history-year">{html.escape(item["year"] or "--")}</div>
                <div class="history-type">{html.escape(item["event_type"] or "历史事件")}</div>
            </div>
            <div class="history-body">
                <div class="history-title">{html.escape(item["title"])}</div>
                <div class="history-summary">{html.escape(item["description"] or "")}</div>
            </div>
        </section>
        """
        for item in items
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                width: 760px;
                padding: 28px;
                background:
                    radial-gradient(circle at top left, rgba(116, 77, 33, 0.12), transparent 32%),
                    radial-gradient(circle at bottom right, rgba(78, 55, 27, 0.08), transparent 28%),
                    linear-gradient(180deg, #d8ccbb 0%, #e8dfd2 52%, #d9cfbf 100%);
                color: #2f251b;
                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            }}
            .board {{
                position: relative;
                overflow: hidden;
                border: 1px solid rgba(96, 69, 39, 0.24);
                border-radius: 24px;
                background:
                    linear-gradient(180deg, rgba(245, 236, 217, 0.98) 0%, rgba(236, 227, 208, 0.98) 100%);
                box-shadow:
                    0 20px 48px rgba(60, 42, 20, 0.16),
                    inset 0 1px 0 rgba(255, 250, 241, 0.55);
            }}
            .paper-grain {{
                position: absolute;
                inset: 0;
                pointer-events: none;
                background:
                    radial-gradient(circle at 12% 18%, rgba(98, 71, 42, 0.08) 0, rgba(98, 71, 42, 0.08) 1px, transparent 1.4px),
                    radial-gradient(circle at 78% 64%, rgba(120, 93, 58, 0.06) 0, rgba(120, 93, 58, 0.06) 1px, transparent 1.6px),
                    repeating-linear-gradient(
                        180deg,
                        rgba(255, 250, 240, 0.06) 0,
                        rgba(255, 250, 240, 0.06) 2px,
                        rgba(145, 113, 74, 0.03) 2px,
                        rgba(145, 113, 74, 0.03) 4px
                    );
                mix-blend-mode: multiply;
                opacity: 0.72;
            }}
            .hero {{
                position: relative;
                padding: 30px 30px 24px;
                background:
                    linear-gradient(135deg, #3d2816 0%, #6f5031 44%, #87613a 100%);
                color: #f6ecda;
                border-bottom: 1px solid rgba(72, 48, 24, 0.34);
            }}
            .hero::after {{
                content: "";
                position: absolute;
                inset: auto -50px -90px auto;
                width: 220px;
                height: 220px;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(232, 196, 134, 0.18) 0%, rgba(232, 196, 134, 0) 72%);
            }}
            .archive-seal {{
                position: absolute;
                right: 22px;
                top: 18px;
                width: 92px;
                height: 92px;
                border-radius: 999px;
                border: 1px solid rgba(248, 225, 187, 0.18);
                background:
                    radial-gradient(circle at 34% 34%, rgba(255, 230, 185, 0.28) 0%, rgba(255, 230, 185, 0.08) 24%, rgba(87, 57, 28, 0) 58%),
                    linear-gradient(135deg, rgba(124, 85, 49, 0.28) 0%, rgba(83, 55, 29, 0.08) 100%);
                box-shadow:
                    inset 0 0 0 1px rgba(255, 243, 219, 0.08),
                    0 10px 26px rgba(27, 16, 7, 0.16);
                opacity: 0.78;
            }}
            .hero-kicker {{
                position: relative;
                z-index: 1;
                font-size: 12px;
                letter-spacing: 1px;
                color: rgba(248, 235, 209, 0.7);
            }}
            .hero-title {{
                position: relative;
                z-index: 1;
                margin-top: 8px;
                font-size: 34px;
                line-height: 1.16;
                font-weight: 700;
                text-shadow: 0 1px 0 rgba(48, 27, 10, 0.22);
            }}
            .hero-meta {{
                position: relative;
                z-index: 1;
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 16px;
            }}
            .hero-chip {{
                padding: 8px 12px;
                border: 1px solid rgba(247, 232, 200, 0.18);
                border-radius: 999px;
                background: rgba(255, 245, 222, 0.08);
                font-size: 13px;
                color: rgba(249, 242, 228, 0.88);
            }}
            .content {{
                padding: 22px;
            }}
            .timeline {{
                position: relative;
                display: grid;
                gap: 14px;
            }}
            .timeline::before {{
                content: "";
                position: absolute;
                left: 92px;
                top: 0;
                bottom: 0;
                width: 2px;
                background: linear-gradient(180deg, rgba(113, 90, 56, 0.5) 0%, rgba(113, 90, 56, 0.12) 100%);
            }}
            .history-card {{
                position: relative;
                display: grid;
                grid-template-columns: 150px minmax(0, 1fr);
                gap: 16px;
                align-items: stretch;
            }}
            .history-mark {{
                position: relative;
                padding: 18px 16px;
                border-radius: 18px;
                border: 1px solid rgba(143, 108, 64, 0.28);
                background: linear-gradient(180deg, rgba(233, 219, 190, 0.98) 0%, rgba(218, 199, 166, 0.96) 100%);
                text-align: center;
                box-shadow:
                    inset 0 1px 0 rgba(255, 248, 234, 0.58),
                    0 8px 18px rgba(73, 54, 31, 0.08);
            }}
            .history-mark::after {{
                content: "";
                position: absolute;
                right: -13px;
                top: 50%;
                width: 10px;
                height: 10px;
                border-radius: 999px;
                background: #6b7b63;
                transform: translateY(-50%);
                box-shadow: 0 0 0 6px rgba(107, 123, 99, 0.14);
            }}
            .history-year {{
                font-size: 28px;
                line-height: 1;
                font-weight: 800;
                color: #634320;
            }}
            .history-type {{
                margin-top: 10px;
                font-size: 12px;
                color: #705a3f;
            }}
            .history-body {{
                padding: 18px 18px 16px;
                border-radius: 18px;
                border: 1px solid rgba(162, 136, 104, 0.24);
                background:
                    linear-gradient(180deg, rgba(248, 241, 227, 0.96) 0%, rgba(240, 231, 214, 0.94) 100%);
                box-shadow:
                    inset 0 1px 0 rgba(255, 250, 242, 0.54),
                    0 10px 24px rgba(71, 51, 29, 0.06);
            }}
            .history-title {{
                font-size: 21px;
                line-height: 1.4;
                font-weight: 700;
                color: #332619;
            }}
            .history-summary {{
                margin-top: 10px;
                font-size: 15px;
                line-height: 1.8;
                color: #5a4834;
                white-space: pre-wrap;
                word-break: break-word;
            }}
        </style>
    </head>
    <body>
        <main class="board">
            <div class="paper-grain"></div>
            <header class="hero">
                <div class="archive-seal"></div>
                <div class="hero-kicker">历史纪事时间轴</div>
                <div class="hero-title">历史上的今天</div>
                <div class="hero-meta">
                    <div class="hero-chip">日期 {html.escape(date_display or "--")}</div>
                    <div class="hero-chip">数据来源 60s API</div>
                </div>
            </header>
            <section class="content">
                <div class="timeline">
                    {cards_html}
                </div>
            </section>
        </main>
    </body>
</html>
"""


def build_digest_html(title: str, date_text: str, source_text: str, item_blocks: list[str]) -> str:
    """构建统一长图 HTML。"""

    items_html = "\n".join(item_blocks)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                width: 760px;
                padding: 28px;
                background: #f5f7fb;
                color: #1f2937;
                font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            }}
            .board {{
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                overflow: hidden;
            }}
            .header {{
                padding: 28px 30px 22px;
                background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
                border-bottom: 1px solid #e5e7eb;
            }}
            .title {{
                font-size: 30px;
                line-height: 1.2;
                font-weight: 700;
                color: #111827;
            }}
            .date {{
                margin-top: 8px;
                font-size: 15px;
                color: #4b5563;
            }}
            .source {{
                margin-top: 8px;
                font-size: 13px;
                color: #6b7280;
            }}
            .content {{
                padding: 18px 22px 26px;
            }}
            .item {{
                padding: 18px 8px;
                border-bottom: 1px solid #eef2f7;
            }}
            .item:last-child {{
                border-bottom: none;
            }}
            .item-title {{
                font-size: 20px;
                line-height: 1.45;
                font-weight: 600;
                color: #111827;
            }}
            .meta {{
                margin-top: 8px;
                font-size: 13px;
                line-height: 1.5;
                color: #6b7280;
            }}
            .summary {{
                margin-top: 10px;
                font-size: 15px;
                line-height: 1.75;
                color: #374151;
                white-space: pre-wrap;
                word-break: break-word;
            }}
        </style>
    </head>
    <body>
        <main class="board">
            <header class="header">
                <div class="title">{html.escape(title)}</div>
                <div class="date">{html.escape(date_text)}</div>
                <div class="source">{html.escape(source_text)}</div>
            </header>
            <section class="content">
                {items_html}
            </section>
        </main>
    </body>
</html>
"""


def _truncate_text(text: str, limit: int) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"
