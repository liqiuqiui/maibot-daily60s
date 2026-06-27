"""每日信息速递插件 — 插件入口，组装 Fetcher、Scheduler 与消息处理器"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Optional, cast

from maibot_sdk import Command, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import HookMode

from .api_registry import API_REGISTRY, CommandUsageError, build_api_request_params, build_command_usage
from .config import Daily60sPluginConfig
from .config_resolver import find_command_match, get_command_keywords, iter_menu_api_names
from .delivery import TargetKind, deliver_fetch_result, deliver_text_to_target
from .fetcher import Fetcher
from .scheduler import Scheduler


@dataclass(frozen=True)
class MessageTarget:
    """从 Host 消息中解析出的发送目标。"""

    kind: TargetKind
    target_id: str


def _build_menu_text(cfg: Daily60sPluginConfig) -> str:
    """根据当前启用的 API 配置生成帮助菜单"""
    lines = [
        "每日信息速递菜单",
        "",
        "可用命令：",
    ]

    menu_api_names = iter_menu_api_names(cfg)
    display_index = 1
    for api_name in menu_api_names:
        definition = API_REGISTRY.get(api_name)
        if definition is None:
            continue

        keywords = get_command_keywords(cfg, api_name)
        if not keywords:
            continue

        command = keywords[0]
        if definition.usage:
            command = f"{command} {definition.usage}"

        aliases = keywords[1:]
        alias_text = f"（别名：{'、'.join(aliases)}）" if aliases else ""
        lines.append(f"{display_index}. {definition.display_name}")
        lines.append(f"   命令：{command}{alias_text}")
        lines.append(f"   作用：{definition.menu_description}")
        display_index += 1

    if not menu_api_names:
        lines.append("当前没有启用的 API 命令")

    lines.extend(
        [
            "",
            "帮助命令：/menu、/help、/菜单、/帮助",
        ]
    )
    return "\n".join(lines)


def _parse_message_target(message: dict[str, Any]) -> MessageTarget | None:
    """从当前 Host 消息结构中解析群聊或私聊目标。"""

    message_info = message.get("message_info") or {}
    if not isinstance(message_info, dict):
        return None

    additional_config = message_info.get("additional_config") or {}
    if not isinstance(additional_config, dict):
        additional_config = {}

    msg_type = additional_config.get("napcat_message_type")
    group_info = message_info.get("group_info") or {}
    user_info = message_info.get("user_info") or {}
    if not isinstance(group_info, dict):
        group_info = {}
    if not isinstance(user_info, dict):
        user_info = {}

    group_id = str(group_info.get("group_id") or "").strip()
    user_id = str(user_info.get("user_id") or "").strip()

    if msg_type == "group" and group_id:
        return MessageTarget(kind="group", target_id=group_id)
    if msg_type == "private" and user_id:
        return MessageTarget(kind="user", target_id=user_id)
    return None


class Daily60sPlugin(MaiBotPlugin):
    """每日信息速递插件：多 API 配置、关键词触发、每 API 独立定时推送"""

    config_model: ClassVar[type[PluginConfigBase] | None] = Daily60sPluginConfig

    def __init__(self) -> None:
        """初始化插件实例，各运行时组件延迟到 on_load 创建"""
        super().__init__()
        self._fetcher: Optional[Fetcher] = None
        self._scheduler: Optional[Scheduler] = None
        self._render_fn = None

    async def on_load(self) -> None:
        """加载插件：初始化 Fetcher 和 Scheduler，启动调度循环"""
        cfg = cast(Daily60sPluginConfig, self.config)
        self.ctx.logger.warning("Daily60sPlugin init")

        self._fetcher = Fetcher(logger=self.ctx.logger, timeout=cfg.fetch.timeout)

        if not cfg.plugin.enabled:
            self.ctx.logger.info("每日信息速递已禁用，不启动定时推送调度器")
            return

        # 图片类内容统一先产出 HTML，再由插件上下文负责截图成 PNG
        # 这里把渲染器闭包保存下来，命令触发和定时推送都复用同一条链路
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
        self.ctx.logger.info("每日信息速递已加载，共 %d 条命令触发规则", len(cfg.command_trigger_config.trigger_list))

    async def on_unload(self) -> None:
        """卸载插件：停止调度循环并清理运行时组件"""
        if self._scheduler is not None:
            await self._scheduler.stop()
            self._scheduler = None
        self._fetcher = None
        self._render_fn = None
        self.ctx.logger.info("每日信息速递已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        """配置更新后重载运行时组件

        Args:
            scope: 配置变更范围
            config_data: 最新配置数据
            version: 配置版本号
        """
        if scope != "self":
            return

        if version:
            self.ctx.logger.debug("每日信息速递收到配置更新通知：%s", version)
        del config_data

        # 重建 Fetcher 和 Scheduler 以使新配置生效
        await self.on_unload()
        await self.on_load()

    @Command(
        "menu",
        description="查看每日信息速递菜单",
        pattern=r"^/(menu|help|菜单|帮助)$",
    )
    async def handle_menu(self, stream_id: str = "", **kwargs: Any):
        """发送每日信息速递帮助菜单"""
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
        """监听消息，匹配任意 API 的关键词后拉取并回复内容

        匹配规则：消息按空格分割，第一个 token 与关键词精确比对（大小写不敏感），
        后续 token 依序对应该 API 在 API_REGISTRY 中定义的 param_names

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

        if not isinstance(message, dict):
            return None

        target = _parse_message_target(message)
        if target is None:
            return None

        raw = str(message.get("processed_plain_text") or "")
        parts = raw.strip().split()
        if not parts:
            return None

        command_token = parts[0].lower()

        matched_command = find_command_match(
            cfg,
            command_token=command_token,
            target_kind=target.kind,
            target_id=target.target_id,
        )
        if matched_command is None:
            return None

        if self._fetcher is None:
            if getattr(self, "_ctx", None) is not None:
                self.ctx.logger.error("插件尚未初始化，无法处理关键词触发请求")
            return None

        # 命令参数解析完全交给 fetcher 里的 registry 定义
        # plugin 只负责把命令 token 切出来，并在解析失败时返回用法提示
        definition = API_REGISTRY.get(matched_command.api_name)
        if definition is None:
            self.ctx.logger.error("API '%s' 不在 API_REGISTRY 中", matched_command.api_name)
            return None

        arg_tokens = parts[1:]
        try:
            params = build_api_request_params(definition, arg_tokens)
        except CommandUsageError:
            usage = build_command_usage(parts[0], definition)
            await deliver_text_to_target(
                ctx=self.ctx,
                target_kind=target.kind,
                target_id=target.target_id,
                text=usage,
            )
            return {"action": "abort"}

        try:
            result = await self._fetcher.fetch(
                api_name=matched_command.api_name,
                base_urls=cfg.fetch.base_urls,
                params=params or None,
                push_format=matched_command.push_type,
            )
            # deliver_fetch_result 会统一处理：
            # 1. 文本直接发送
            # 2. HTML 先 render 成图片
            # 3. 图片按 group/user 分流
            await deliver_fetch_result(
                ctx=self.ctx,
                target_kind=target.kind,
                target_id=target.target_id,
                result=result,
                render_fn=self._render_fn,
            )
        except Exception:
            self.ctx.logger.exception("拉取 API '%s' 失败", matched_command.api_name)
            await deliver_text_to_target(
                ctx=self.ctx,
                target_kind=target.kind,
                target_id=target.target_id,
                text="内容获取失败，请稍后重试",
            )

        return {"action": "abort"}
