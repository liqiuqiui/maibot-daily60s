"""每日速读插件 — OneBot HTTP 消息发送器。"""

from __future__ import annotations

import logging
import urllib.parse
from urllib.parse import urlencode

import aiohttp

LOGGER = logging.getLogger("daily60s.sender")


class OneBotSender:
    """OneBot HTTP API 消息发送器。

    通过 POST /send_msg 接口向 OneBot 服务发送群消息和私聊消息。

    Args:
        host: OneBot HTTP 服务地址，含协议前缀，例如 http://127.0.0.1。
        port: 端口号。
        token: access token，为空时不附加鉴权参数。
        timeout: HTTP 请求超时秒数。
    """

    def __init__(self, host: str, port: int, token: str, timeout: int) -> None:
        # 解析 host，防止用户填入 "http://127.0.0.1:5700" 导致双重端口拼接
        parsed = urllib.parse.urlsplit(host)
        self._base_url = f"{parsed.scheme}://{parsed.hostname}:{port}"
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    def _build_url(self, action: str) -> str:
        """构造完整请求 URL，token 非空时附加 access_token 查询参数。"""
        url = f"{self._base_url}/{action}"
        if self._token:
            url += "?" + urlencode({"access_token": self._token})
        return url

    async def _post(self, payload: dict) -> None:
        """发送 JSON POST 请求，失败时记录 warning 不抛出异常。"""
        url = self._build_url("send_msg")
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        LOGGER.warning("OneBot 请求失败，HTTP %d，payload=%s", resp.status, payload)
                        return
                    data = await resp.json(content_type=None)
                    if data.get("status") not in ("ok", "async"):
                        LOGGER.warning(
                            "OneBot 返回失败状态：status=%s retcode=%s，payload=%s",
                            data.get("status"),
                            data.get("retcode"),
                            payload,
                        )
        except Exception:
            LOGGER.warning("发送 OneBot 消息时发生异常，payload=%s", payload, exc_info=True)

    async def send_group(self, group_id: int, message: str) -> None:
        """发送群消息。

        Args:
            group_id: QQ 群号。
            message: 消息文本内容。
        """
        await self._post({"message_type": "group", "group_id": group_id, "message": message})

    async def send_user(self, user_id: int, message: str) -> None:
        """发送私聊消息。

        Args:
            user_id: 私聊 QQ 号。
            message: 消息文本内容。
        """
        await self._post({"message_type": "private", "user_id": user_id, "message": message})

    async def send_group_image(self, group_id: int, image_b64: str) -> None:
        """发送群图片消息（CQ 码格式）。

        Args:
            group_id: QQ 群号。
            image_b64: 图片 base64 编码字符串。
        """
        message = f"[CQ:image,file=base64://{image_b64}]"
        await self._post({"message_type": "group", "group_id": group_id, "message": message})

    async def send_user_image(self, user_id: int, image_b64: str) -> None:
        """发送私聊图片消息（CQ 码格式）。

        Args:
            user_id: 私聊 QQ 号。
            image_b64: 图片 base64 编码字符串。
        """
        message = f"[CQ:image,file=base64://{image_b64}]"
        await self._post({"message_type": "private", "user_id": user_id, "message": message})
