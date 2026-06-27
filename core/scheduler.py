"""每日信息速递插件 — 定时推送调度器"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from logging import Logger
from typing import Any

import asyncio

from maibot_sdk.context import PluginContext

from .api_registry import API_REGISTRY
from .config import Daily60sPluginConfig, TargetFilterType
from .config_resolver import ScheduleTask, iter_schedule_tasks
from .delivery import RenderFn, deliver_fetch_result
from .fetcher import Fetcher

# 调度循环检查间隔（秒）
_CHECK_INTERVAL_SEC = 10


def _normalize_time(time_str: str) -> str:
    """规范化时间字符串为 HH:MM 格式

    Args:
        time_str: 时间字符串，可能不是标准的两位格式

    Returns:
        str: 标准化的 HH:MM 格式时间字符串
    """
    try:
        # 解析时间，然后重新格式化为标准格式
        dt = datetime.strptime(time_str, "%H:%M")
        return dt.strftime("%H:%M")
    except ValueError:
        # 如果解析失败，返回原字符串
        return time_str


class Scheduler:
    """每日定时推送调度器

    每条定时配置可包含多个 API，调度器会展开为单 API 任务后统一检查
    推送目标通过 QQ 群号 / 私聊 QQ 号配置，使用插件上下文的 send 能力发送

    Args:
        logger: 日志记录器
        ctx: 插件运行时上下文
        config: 插件完整配置
        fetcher: 已初始化的数据源拉取器
        render_fn: 可选的 HTML→PNG 渲染函数，用于渲染图片消息
    """

    def __init__(
        self,
        logger: Logger,
        ctx: PluginContext,
        config: Daily60sPluginConfig,
        fetcher: Fetcher,
        render_fn: RenderFn | None = None,
    ) -> None:
        self._logger = logger
        self._ctx = ctx
        self._config = config
        self._fetcher = fetcher
        self._render_fn = render_fn
        self._task: asyncio.Task[None] | None = None
        self._push_tasks: set[asyncio.Task[None]] = set()
        # 记录每个定时任务当天是否已推送，键包含 API、时间和目标，值为最后推送日期 YYYY-MM-DD
        self._last_push_date: dict[str, str] = {}
        # 记录每个定时任务是否正在推送中，避免重复触发
        self._pushing: dict[str, bool] = {}

    def start(self) -> None:
        """启动定时调度后台任务"""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        self._logger.info("定时推送调度器已启动，当前启用 %d 条定时任务", self._count_enabled_schedule_tasks())

    async def stop(self) -> None:
        """取消并等待调度后台任务结束"""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

        if self._push_tasks:
            push_tasks = tuple(self._push_tasks)
            for push_task in push_tasks:
                push_task.cancel()
            await asyncio.gather(*push_tasks, return_exceptions=True)
            self._push_tasks.clear()
        self._logger.info("定时推送调度器已停止")

    async def _loop(self) -> None:
        """调度主循环：每 60 秒检查一次所有启用定时推送的 API"""
        # 预校验所有需要定时推送的 API 的 push_time 格式
        self._validate_push_times()

        while True:
            try:
                await asyncio.sleep(_CHECK_INTERVAL_SEC)
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M")

                for task in iter_schedule_tasks(self._config):
                    # 规范化推送时间，确保格式一致
                    push_time = _normalize_time(task.push_time)
                    # 只有当前时间小于推送时间时才跳过，否则执行推送
                    # 这样即使错过了精确的推送时间，也能在后续检查中触发
                    if current_time < push_time:
                        continue
                    task_key = self._build_task_key(task)
                    if self._last_push_date.get(task_key) == today:
                        continue
                    # 这里只负责"到点了可以推"，真正是否记为已推送，
                    # 要等 _do_push 至少成功投递到一个目标后再写入 _last_push_date
                    self._schedule_push_task(task)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("定时推送循环发生异常，继续运行")

    def _validate_push_times(self) -> None:
        """校验所有启用定时任务的 push_time 格式，非法时记录错误"""
        for task in iter_schedule_tasks(self._config):
            try:
                datetime.strptime(task.push_time, "%H:%M")
            except ValueError:
                self._logger.error(
                    "API '%s' 的 push_time 格式非法：'%s'，该 API 的定时推送将不会触发。",
                    task.api_name,
                    task.push_time,
                )

    def _count_enabled_schedule_tasks(self) -> int:
        """统计当前启用的定时推送任务数量"""

        return len(iter_schedule_tasks(self._config))

    def _schedule_push_task(self, task: ScheduleTask) -> bool:
        """创建并托管单个推送任务"""
        task_key = self._build_task_key(task)
        if self._pushing.get(task_key, False):
            self._logger.debug("API '%s' 正在推送中，跳过本次调度", task.api_name)
            return False

        self._pushing[task_key] = True
        push_task = asyncio.create_task(self._do_push(task, task_key=task_key))
        self._push_tasks.add(push_task)
        push_task.add_done_callback(self._push_tasks.discard)
        return True

    async def _do_push(self, task: ScheduleTask, task_key: str | None = None) -> None:
        """执行单个 API 的定时推送任务

        遍历 groups（群号）和 users（私聊 QQ 号），使用插件上下文的 send 能力发送

        Args:
            task: 展开后的单 API 定时推送任务
            task_key: 已占用的运行时去重键
        """
        task_key_reserved = task_key is not None
        task_key = task_key or self._build_task_key(task)

        if not task_key_reserved and self._pushing.get(task_key, False):
            self._logger.debug("API '%s' 正在推送中，跳过本次推送", task.api_name)
            return

        self._pushing[task_key] = True

        try:
            if not self._config.plugin.enabled:
                self._logger.info("每日信息速递已禁用，跳过定时推送")
                return

            groups = await self._resolve_schedule_targets(
                filter_type=task.groups_type,
                configured_targets=task.groups,
                stream_loader=self._ctx.chat.get_group_streams,
                target_field="group_id",
                nested_info_field="group_info",
            )
            users = await self._resolve_schedule_targets(
                filter_type=task.users_type,
                configured_targets=task.users,
                stream_loader=self._ctx.chat.get_private_streams,
                target_field="user_id",
                nested_info_field="user_info",
            )

            if not groups and not users:
                self._logger.info("API '%s' 的推送群聊和私聊目标均为空，跳过定时推送", task.api_name)
                return

            if task.api_name not in API_REGISTRY:
                self._logger.error("API '%s' 不在 API_REGISTRY 中，无法推送", task.api_name)
                return

            self._logger.info("开始定时推送 API '%s'", task.api_name)
            result = await self._fetcher.fetch(
                api_name=task.api_name,
                base_urls=self._config.fetch.base_urls,
                push_format=task.push_type,
            )

            # 只要任意一个群/用户发送成功，就视为本轮推送完成，避免重复轰炸
            # 如果全部失败，则不写去重标记，让下一轮仍有机会重试
            delivered = False

            # 推送至各个群
            for group_id in groups:
                try:
                    if await deliver_fetch_result(
                        ctx=self._ctx,
                        target_kind="group",
                        target_id=group_id,
                        result=result,
                        render_fn=self._render_fn,
                    ):
                        delivered = True
                except Exception:
                    self._logger.warning("向群 '%s' 推送 API '%s' 失败", group_id, task.api_name, exc_info=True)

            # 推送至各个私聊用户
            for user_id in users:
                try:
                    if await deliver_fetch_result(
                        ctx=self._ctx,
                        target_kind="user",
                        target_id=user_id,
                        result=result,
                        render_fn=self._render_fn,
                    ):
                        delivered = True
                except Exception:
                    self._logger.warning("向用户 '%s' 推送 API '%s' 失败", user_id, task.api_name, exc_info=True)

            if delivered:
                self._last_push_date[task_key] = datetime.now().strftime("%Y-%m-%d")

        except Exception:
            self._logger.exception("定时推送 API '%s' 失败", task.api_name)
        finally:
            # 清除推送状态
            self._pushing[task_key] = False
            self._logger.debug("API '%s' 推送完成，状态已重置", task.api_name)

    def _build_task_key(self, task: ScheduleTask) -> str:
        """构造单个定时任务的运行时去重键"""
        groups = ",".join(task.groups)
        users = ",".join(task.users)
        return (
            f"{task.api_name}|{task.push_time}|{task.push_type}|"
            f"gt:{task.groups_type}|g:{groups}|ut:{task.users_type}|u:{users}"
        )

    async def _resolve_schedule_targets(
        self,
        *,
        filter_type: TargetFilterType,
        configured_targets: tuple[str, ...],
        stream_loader: Callable[[], Awaitable[Any]],
        target_field: str,
        nested_info_field: str,
    ) -> tuple[str, ...]:
        """解析定时推送目标。

        whitelist 使用显式配置；blacklist 从 Host 已有聊天流中取全量目标后扣除配置名单。
        """

        configured = self._dedupe_targets(configured_targets)
        if filter_type == "whitelist":
            return configured

        streams = await stream_loader()
        stream_targets = self._extract_targets_from_streams(
            streams=streams,
            target_field=target_field,
            nested_info_field=nested_info_field,
        )
        blocked = set(configured)
        return tuple(target_id for target_id in stream_targets if target_id not in blocked)

    @staticmethod
    def _dedupe_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
        """保持顺序去重并过滤空目标。"""

        result: list[str] = []
        seen: set[str] = set()
        for target in targets:
            normalized_target = str(target).strip()
            if not normalized_target or normalized_target in seen:
                continue
            seen.add(normalized_target)
            result.append(normalized_target)
        return tuple(result)

    @classmethod
    def _extract_targets_from_streams(
        cls,
        *,
        streams: Any,
        target_field: str,
        nested_info_field: str,
    ) -> tuple[str, ...]:
        """从聊天流列表中提取群号或用户 ID。"""

        if not isinstance(streams, list):
            return ()

        targets: list[str] = []
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            target_value = stream.get(target_field)
            if not target_value:
                nested_info = stream.get(nested_info_field)
                if isinstance(nested_info, dict):
                    target_value = nested_info.get(target_field)
            if target_value:
                targets.append(str(target_value))
        return cls._dedupe_targets(tuple(targets))
