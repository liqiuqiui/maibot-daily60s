"""每日速读插件 — 定时推送调度器。"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any, Optional

import asyncio
from logging import Logger

from .config import ApiConfig, Daily60sPluginConfig
from .fetcher import API_REGISTRY, Fetcher
from .sender import OneBotSender

# 调度循环检查间隔（秒）
_CHECK_INTERVAL_SEC = 60

RenderFn = Callable[[str], Coroutine[Any, Any, str]]
"""签名：async def render_fn(html: str) -> str（返回 base64 PNG）"""


class Scheduler:
    """每日定时推送调度器。

    每个 API 独立配置推送时间和目标群聊，调度器统一在后台循环中检查。
    推送目标通过 QQ 群号 / 私聊 QQ 号配置，直接通过 OneBotSender 发送。

    Args:
        logger: 日志记录器。
        config: 插件完整配置。
        fetcher: 已初始化的数据源拉取器。
        sender: OneBot HTTP 消息发送器。
        render_fn: 可选的 HTML→PNG 渲染函数，用于渲染图片消息。
    """

    def __init__(
        self,
        logger: Logger,
        config: Daily60sPluginConfig,
        fetcher: Fetcher,
        sender: OneBotSender,
        render_fn: Optional[RenderFn] = None,
    ) -> None:
        self._logger = logger
        self._config = config
        self._fetcher = fetcher
        self._sender = sender
        self._render_fn = render_fn
        self._task: asyncio.Task[None] | None = None
        # 记录每个 API 当天是否已推送，键为 api_name，值为最后推送日期 YYYY-MM-DD
        self._last_push_date: dict[str, str] = {}

    def start(self) -> None:
        """启动定时调度后台任务。"""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        self._logger.info("定时推送调度器已启动")

    async def stop(self) -> None:
        """取消并等待调度后台任务结束。"""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        self._logger.info("定时推送调度器已停止")

    async def _loop(self) -> None:
        """调度主循环：每 60 秒检查一次所有启用定时推送的 API。"""
        # 预校验所有需要定时推送的 API 的 push_time 格式
        self._validate_push_times()

        while True:
            try:
                await asyncio.sleep(_CHECK_INTERVAL_SEC)
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M")

                for api in self._config.apis:
                    if not api.enabled or not api.schedule_push:
                        continue
                    if current_time != api.push_time:
                        continue
                    if self._last_push_date.get(api.name) == today:
                        continue
                    # 记录推送日期，避免同日重复
                    self._last_push_date[api.name] = today
                    # 异步触发推送，不阻塞循环继续检查其他 API
                    asyncio.create_task(self._do_push(api))
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("定时推送循环发生异常，继续运行")

    def _validate_push_times(self) -> None:
        """校验所有启用定时推送的 API 的 push_time 格式，非法时记录错误。"""
        for api in self._config.apis:
            if not api.enabled or not api.schedule_push:
                continue
            try:
                datetime.strptime(api.push_time, "%H:%M")
            except ValueError:
                self._logger.error(
                    "API '%s' 的 push_time 格式非法：'%s'，该 API 的定时推送将不会触发。",
                    api.name,
                    api.push_time,
                )

    async def _do_push(self, api: ApiConfig) -> None:
        """执行单个 API 的定时推送。

        遍历 push_groups（群号）和 push_users（私聊 QQ 号），分别调用 OneBotSender 发送。

        Args:
            api: 需要推送的 API 配置。
        """
        if not api.push_groups and not api.push_users:
            self._logger.info("API '%s' 的 push_groups 和 push_users 均为空，跳过定时推送", api.name)
            return

        if api.name not in API_REGISTRY:
            self._logger.error("API '%s' 不在 API_REGISTRY 中，无法推送", api.name)
            return

        self._logger.info("开始定时推送 API '%s'", api.name)
        push_format = getattr(api, "push_format", "text")
        try:
            result = await self._fetcher.fetch(
                api_name=api.name,
                base_urls=self._config.fetch.base_urls,
                push_format=push_format,
            )
        except Exception:
            self._logger.exception("定时推送拉取 API '%s' 失败，跳过", api.name)
            return

        # 推送至各个群
        for group_id in api.push_groups:
            try:
                content = await self._resolve_content(result.content, result.html)
                if result.is_image:
                    await self._sender.send_group_image(int(group_id), content)
                else:
                    await self._sender.send_group(int(group_id), content)
            except Exception:
                self._logger.warning("向群 '%s' 推送 API '%s' 失败", group_id, api.name, exc_info=True)

        # 推送至各个私聊用户
        for user_id in api.push_users:
            try:
                content = await self._resolve_content(result.content, result.html)
                if result.is_image:
                    await self._sender.send_user_image(int(user_id), content)
                else:
                    await self._sender.send_user(int(user_id), content)
            except Exception:
                self._logger.warning("向用户 '%s' 推送 API '%s' 失败", user_id, api.name, exc_info=True)

    async def _resolve_content(self, content: str, html: str) -> str:
        """将 FetchResult 的 html 字段渲染为 base64，或直接返回 content。

        Args:
            content: 文本内容或已有 base64 图片字符串。
            html: 待渲染的 HTML，非空时调用 render_fn 渲染。

        Returns:
            str: 最终内容（base64 或文本）。
        """
        if html and self._render_fn:
            return await self._render_fn(html)
        return content
