"""每日信息速递插件 — 插件入口，组装 Fetcher、Scheduler 与消息处理器。"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, cast

from maibot_sdk import Command, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import HookMode

from .config import ApiConfig, Daily60sPluginConfig
from .delivery import deliver_fetch_result
from .fetcher import API_REGISTRY, CommandUsageError, Fetcher, build_api_request_params, build_command_usage
from .scheduler import Scheduler


def _build_menu_text(cfg: Daily60sPluginConfig) -> str:
    """根据当前启用的 API 配置生成帮助菜单。"""
    lines = [
        "每日信息速递菜单",
        "",
        "可用命令：",
    ]

    enabled_api_count = 0
    for api in cfg.apis:
        if not api.enabled:
            continue

        definition = API_REGISTRY.get(api.name)
        if definition is None:
            continue

        keywords = [keyword for keyword in api.keywords if keyword]
        if not keywords:
            continue

        enabled_api_count += 1
        command = keywords[0]
        if definition.usage:
            command = f"{command} {definition.usage}"

        aliases = keywords[1:]
        alias_text = f"（别名：{'、'.join(aliases)}）" if aliases else ""
        lines.append(f"- {command}{alias_text}")

    if enabled_api_count == 0:
        lines.append("- 当前没有启用的 API 命令")

    lines.extend(
        [
            "",
            "帮助命令：/menu、/help、/菜单、/帮助",
        ]
    )
    return "\n".join(lines)


class Daily60sPlugin(MaiBotPlugin):
    """每日信息速递插件：多 API 配置、关键词触发、每 API 独立定时推送。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = Daily60sPluginConfig

    def __init__(self) -> None:
        """初始化插件实例，各运行时组件延迟到 on_load 创建。"""
        super().__init__()
        self._fetcher: Optional[Fetcher] = None
        self._scheduler: Optional[Scheduler] = None
        self._render_fn = None

    async def on_load(self) -> None:
        """加载插件：初始化 Fetcher 和 Scheduler，启动调度循环。"""
        cfg = cast(Daily60sPluginConfig, self.config)
        self.ctx.logger.warning("Daily60sPlugin init")

        self._fetcher = Fetcher(logger=self.ctx.logger, timeout=cfg.fetch.timeout)

        # 图片类内容统一先产出 HTML，再由插件上下文负责截图成 PNG。
        # 这里把渲染器闭包保存下来，命令触发和定时推送都复用同一条链路。
        async def _render_fn(html: str) -> str:
            result = await self.ctx.render.html2png(html, selector="body", device_scale_factor=2.0)
            return result["image_base64"]

        self._render_fn = _render_fn
        self._scheduler = Scheduler(
            logger=self.ctx.logger,
            ctx=self.ctx,
            config=cfg,
            fetcher=self._fetcher,
            render_fn=_render_fn,
        )
        self._scheduler.start()
        self.ctx.logger.info("每日信息速递已加载，共 %d 个 API", len(cfg.apis))

    async def on_unload(self) -> None:
        """卸载插件：停止调度循环并清理运行时组件。"""
        if self._scheduler is not None:
            await self._scheduler.stop()
            self._scheduler = None
        self._fetcher = None
        self._render_fn = None
        self.ctx.logger.info("每日信息速递已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        """配置更新后重载运行时组件。

        Args:
            scope: 配置变更范围。
            config_data: 最新配置数据。
            version: 配置版本号。
        """
        if scope != "self":
            return

        self.set_plugin_config(config_data)
        if version:
            self.ctx.logger.debug("每日信息速递收到配置更新通知：%s", version)

        # 重建 Fetcher 和 Scheduler 以使新配置生效
        await self.on_unload()
        await self.on_load()

    @Command(
        "daily60s_menu",
        description="查看每日信息速递菜单",
        pattern=r"^/(menu|help|菜单|帮助)$",
    )
    async def handle_menu(self, stream_id: str = "", **kwargs: Any):
        """发送每日信息速递帮助菜单。"""
        del kwargs

        cfg = cast(Daily60sPluginConfig, self.config)
        if not cfg.plugin.enabled:
            return False, "每日信息速递未启用", False

        await self.ctx.send.text(text=_build_menu_text(cfg), stream_id=stream_id)
        return True, "菜单已发送", True

    @HookHandler(
        hook="chat.receive.before_process",
        name="daily60s_message_handler",
        description="关键词触发 API 查询",
        mode=HookMode.BLOCKING,
    )
    async def handle_message(self, **kwargs: Any):
        """监听消息，匹配任意 API 的关键词后拉取并回复内容。

        匹配规则：消息按空格分割，第一个 token 与关键词精确比对（大小写不敏感），
        后续 token 依序对应该 API 在 API_REGISTRY 中定义的 param_names。

        Args:
            **kwargs: SessionMessage消息参数

        Returns:
        """

        message = kwargs.get("message")
        if message is None:
            return None

        cfg = cast(Daily60sPluginConfig, self.config)

        if not message.get("is_command") or not cfg.plugin.enabled:
            return None

        # OneBot 上下文里，群聊和私聊的目标 ID 放在不同字段。
        # 这里先把原始 message_info 拆开，后面路由和发送都只用 group_id / user_id。
        message_info = message.get("message_info") or {}
        if not isinstance(message_info, dict):
            return None
        additional_config = message_info.get("additional_config") or {}
        if not isinstance(additional_config, dict):
            additional_config = {}
        msg_type = additional_config.get("napcat_message_type")
        group_info = message_info.get("group_info") or {}
        user_info = message_info.get("user_info") or {}
        group_id: str = group_info.get("group_id", "")
        user_id: str = user_info.get("user_id", "")

        if msg_type == "group" and not group_id:
            return None
        if msg_type == "private" and not user_id:
            return None

        raw = message.get("processed_plain_text", "") if isinstance(message, dict) else str(message)
        parts = raw.strip().split()
        if not parts:
            return None

        command_token = parts[0].lower()

        # 配置层仍然保持"一 API 一配置块"，但运行时只按统一 apis 列表扫描，
        # 这样新增模块时不用改命令路由骨架。
        matched_api: Optional[ApiConfig] = None
        for api in cfg.apis:
            if not api.enabled:
                continue
            for keyword in api.keywords:
                if command_token == keyword.lower():
                    matched_api = api
                    break
            if matched_api is not None:
                break

        if matched_api is None:
            return None

        if self._fetcher is None:
            if getattr(self, "_ctx", None) is not None:
                self.ctx.logger.error("插件尚未初始化，无法处理关键词触发请求")
            return None

        # 命令参数解析完全交给 fetcher 里的 registry 定义。
        # plugin 只负责把命令 token 切出来，并在解析失败时返回用法提示。
        definition = API_REGISTRY.get(matched_api.name)
        if definition is None:
            self.ctx.logger.error("API '%s' 不在 API_REGISTRY 中", matched_api.name)
            return None

        arg_tokens = parts[1:]
        try:
            params = build_api_request_params(definition, arg_tokens)
        except CommandUsageError:
            usage = build_command_usage(parts[0], definition)
            # 使用 ctx.send 发送用法提示
            if msg_type == "private":
                await self.ctx.send.text(text=usage, stream_id=user_id)
            elif msg_type == "group":
                await self.ctx.send.text(text=usage, stream_id=group_id)
            return None

        push_format = getattr(matched_api, "push_format", "text")
        try:
            result = await self._fetcher.fetch(
                api_name=matched_api.name,
                base_urls=cfg.fetch.base_urls,
                params=params or None,
                push_format=push_format,
            )
            # deliver_fetch_result 会统一处理：
            # 1. 文本直接发送
            # 2. HTML 先 render 成图片
            # 3. 图片按 group/user 分流
            if msg_type == "private":
                await deliver_fetch_result(
                    ctx=self.ctx,
                    target_kind="user",
                    target_id=user_id,
                    result=result,
                    render_fn=self._render_fn,
                )
            elif msg_type == "group":
                await deliver_fetch_result(
                    ctx=self.ctx,
                    target_kind="group",
                    target_id=group_id,
                    result=result,
                    render_fn=self._render_fn,
                )
        except Exception:
            self.ctx.logger.exception("拉取 API '%s' 失败", matched_api.name)
            if msg_type == "private":
                await self.ctx.send.text(text="内容获取失败，请稍后重试", stream_id=user_id)
            else:
                await self.ctx.send.text(text="内容获取失败，请稍后重试", stream_id=group_id)

        return {"action": "abort"}


def create_plugin() -> Daily60sPlugin:
    """创建每日信息速递插件实例。

    Returns:
        Daily60sPlugin: 插件实例。
    """
    return Daily60sPlugin()
