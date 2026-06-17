"""每日速读插件 — 插件入口，组装 Fetcher、Scheduler 与消息处理器。"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, cast
import json

from maibot_sdk import EventHandler, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import EventType, HookMode

from .config import ApiConfig, Daily60sPluginConfig
from .fetcher import API_REGISTRY, Fetcher
from .scheduler import Scheduler
from .sender import OneBotSender


class Daily60sPlugin(MaiBotPlugin):
    """每日速读插件：多 API 配置、关键词触发、每 API 独立定时推送。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = Daily60sPluginConfig

    def __init__(self) -> None:
        """初始化插件实例，各运行时组件延迟到 on_load 创建。"""
        super().__init__()
        self._fetcher: Optional[Fetcher] = None
        self._scheduler: Optional[Scheduler] = None
        self._sender: Optional[OneBotSender] = None

    async def on_load(self) -> None:
        """加载插件：初始化 Fetcher、OneBotSender 和 Scheduler，启动调度循环。"""
        cfg = cast(Daily60sPluginConfig, self.config)
        self.ctx.logger.warning("Daily60sPlugin init")

        self._fetcher = Fetcher(timeout=cfg.fetch.timeout)
        self._sender = OneBotSender(
            logger=self.ctx.logger,
            host=cfg.message_server.host,
            port=cfg.message_server.port,
            token=cfg.message_server.token,
            timeout=cfg.fetch.timeout,
        )

        self._scheduler = Scheduler(
            logger=self.ctx.logger,
            config=cfg,
            fetcher=self._fetcher,
            sender=self._sender,
        )
        self._scheduler.start()
        self.ctx.logger.info("每日速读插件已加载，共 %d 个 API", len(cfg.apis))

    async def on_unload(self) -> None:
        """卸载插件：停止调度循环并清理运行时组件。"""
        if self._scheduler is not None:
            await self._scheduler.stop()
            self._scheduler = None
        self._fetcher = None
        self._sender = None
        self.ctx.logger.info("每日速读插件已卸载")

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
            self.ctx.logger.debug("每日速读插件收到配置更新通知：%s", version)

        # 重建 Fetcher 和 Scheduler 以使新配置生效
        await self.on_unload()
        await self.on_load()

    @EventHandler(
        "on_startup",
        description="插件启动时初始化资源",
        event_type=EventType.ON_START,
    )
    async def handle_startup(self, **kwargs):
        self.ctx.logger.info("启动事件触发，开始初始化")
        # 在这里执行启动时需要的初始化逻辑

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
        self.ctx.logger.info(f"接受消息:\n {json.dumps(obj=message, indent=2, ensure_ascii=False)}")
        cfg = cast(Daily60sPluginConfig, self.config)

        if not message.get("is_command") or not cfg.plugin.enabled:
            return None

        # 根据消息类型取发送目标 ID
        msg_type = message.get("message_info", {}).get("additional_config", "").get("napcat_message_type")
        group_info = message.get("message_info", {}).get("group_info") or {}
        user_info = message.get("message_info", {}).get("user_info") or {}
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

        # 在所有启用的 API 中查找匹配的关键词
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

        if self._fetcher is None or self._sender is None:
            self.ctx.logger.error("插件尚未初始化，无法处理关键词触发请求")
            return None

        # 从 API_REGISTRY 取参数名定义，按位置从消息 token 中提取参数值
        definition = API_REGISTRY.get(matched_api.name)
        if definition is None:
            self.ctx.logger.error("API '%s' 不在 API_REGISTRY 中", matched_api.name)
            return None

        params: dict[str, str] = {}
        arg_tokens = parts[1:]
        for i, param_name in enumerate(definition.param_names):
            if i < len(arg_tokens):
                params[param_name] = arg_tokens[i]
            else:
                # 必填参数缺失，回复用法提示
                usage = f"用法：{parts[0]} " + " ".join(f"<{n}>" for n in definition.param_names)
                if msg_type == "private":
                    await self._sender.send_user(int(user_id), usage)
                else:
                    await self._sender.send_group(int(group_id), usage)
                return None

        push_format = getattr(matched_api, "push_format", "text")
        try:
            result = await self._fetcher.fetch(
                api_name=matched_api.name,
                base_urls=cfg.fetch.base_urls,
                params=params or None,
                push_format=push_format,
            )
            if msg_type == "private":
                if result.is_image:
                    await self._sender.send_user_image(int(user_id), result.content)
                else:
                    await self._sender.send_user(int(user_id), result.content)
            else:
                if result.is_image:
                    await self._sender.send_group_image(int(group_id), result.content)
                else:
                    await self._sender.send_group(int(group_id), result.content)
        except Exception:
            self.ctx.logger.exception("拉取 API '%s' 失败", matched_api.name)
            if msg_type == "private":
                await self._sender.send_user(int(user_id), "内容获取失败，请稍后重试")
            else:
                await self._sender.send_group(int(group_id), "内容获取失败，请稍后重试")

        return {"action": "abort"}


def create_plugin() -> Daily60sPlugin:
    """创建每日速读插件实例。

    Returns:
        Daily60sPlugin: 插件实例。
    """
    return Daily60sPlugin()
