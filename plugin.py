"""每日速读插件 — 插件入口，组装 Fetcher、Scheduler 与消息处理器。"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, cast

import logging

from maibot_sdk import EventHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import EventType

from .config import ApiConfig, Daily60sPluginConfig
from .fetcher import API_REGISTRY, Fetcher
from .scheduler import Scheduler

LOGGER = logging.getLogger("daily60s.plugin")


class Daily60sPlugin(MaiBotPlugin):
    """每日速读插件：多 API 配置、关键词触发、每 API 独立定时推送。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = Daily60sPluginConfig

    def __init__(self) -> None:
        """初始化插件实例，各运行时组件延迟到 on_load 创建。"""
        super().__init__()
        self._fetcher: Optional[Fetcher] = None
        self._scheduler: Optional[Scheduler] = None

    async def on_load(self) -> None:
        """加载插件：初始化 Fetcher 和 Scheduler，启动调度循环。"""
        cfg = cast(Daily60sPluginConfig, self.config)

        self._fetcher = Fetcher(timeout=cfg.fetch.timeout)

        async def _send_text(content: str, stream_id: str) -> None:
            await self.ctx.send.text(content, stream_id)

        async def _send_image(content: str, stream_id: str) -> None:
            await self.ctx.send.image(content, stream_id)

        self._scheduler = Scheduler(
            config=cfg,
            fetcher=self._fetcher,
            send_text_fn=_send_text,
            send_image_fn=_send_image,
        )
        self._scheduler.start()
        LOGGER.info("每日速读插件已加载，共 %d 个 API", len(cfg.apis))

    async def on_unload(self) -> None:
        """卸载插件：停止调度循环并清理运行时组件。"""
        if self._scheduler is not None:
            await self._scheduler.stop()
            self._scheduler = None
        self._fetcher = None
        LOGGER.info("每日速读插件已卸载")

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
            LOGGER.debug("每日速读插件收到配置更新通知：%s", version)

        # 重建 Fetcher 和 Scheduler 以使新配置生效
        await self.on_unload()
        await self.on_load()

    @EventHandler(
        "daily60s_message_handler",
        description="关键词触发 API 查询",
        event_type=EventType.ON_MESSAGE,
    )
    async def handle_message(
        self,
        message: Any = None,
        stream_id: str = "",
        **kwargs: Any,
    ) -> tuple:
        """监听消息，匹配任意 API 的关键词后拉取并回复内容。

        匹配规则：消息按空格分割，第一个 token 与关键词精确比对（大小写不敏感），
        后续 token 依序对应该 API 在 API_REGISTRY 中定义的 param_names。

        Args:
            message: 消息对象，包含 plain_text 等字段。
            stream_id: 消息来源的聊天流 ID。
            **kwargs: 预留扩展参数。

        Returns:
            tuple: SDK 规定的标准返回格式。
        """
        del kwargs

        cfg = cast(Daily60sPluginConfig, self.config)
        if not cfg.plugin.enabled:
            return True, True, None, None, None

        if not message or not stream_id:
            return True, True, None, None, None

        raw = message.get("plain_text", "") if isinstance(message, dict) else str(message)
        parts = raw.strip().split()
        if not parts:
            return True, True, None, None, None

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
            return True, True, None, None, None

        if self._fetcher is None:
            LOGGER.error("Fetcher 尚未初始化，无法处理关键词触发请求")
            return True, True, None, None, None

        # 从 API_REGISTRY 取参数名定义，按位置从消息 token 中提取参数值
        definition = API_REGISTRY.get(matched_api.name)
        if definition is None:
            LOGGER.error("API '%s' 不在 API_REGISTRY 中", matched_api.name)
            return True, True, None, None, None

        params: dict[str, str] = {}
        arg_tokens = parts[1:]
        for i, param_name in enumerate(definition.param_names):
            if i < len(arg_tokens):
                params[param_name] = arg_tokens[i]
            else:
                # 必填参数缺失，回复用法提示
                usage = f"用法：{parts[0]} " + " ".join(f"<{n}>" for n in definition.param_names)
                await self.ctx.send.text(usage, stream_id)
                return True, True, None, None, None

        push_format = getattr(matched_api, "push_format", "text")
        try:
            result = await self._fetcher.fetch(
                api_name=matched_api.name,
                base_urls=cfg.fetch.base_urls,
                params=params or None,
                push_format=push_format,
            )
            if result.is_image:
                await self.ctx.send.image(result.content, stream_id)
            else:
                await self.ctx.send.text(result.content, stream_id)
        except Exception:
            LOGGER.exception("拉取 API '%s' 失败", matched_api.name)
            await self.ctx.send.text("内容获取失败，请稍后重试", stream_id)

        return True, True, None, None, None


def create_plugin() -> Daily60sPlugin:
    """创建每日速读插件实例。

    Returns:
        Daily60sPlugin: 插件实例。
    """
    return Daily60sPlugin()
