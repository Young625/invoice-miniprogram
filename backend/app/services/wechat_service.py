"""微信小程序服务"""
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WeChatService:
    """微信小程序服务"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.session_url = "https://api.weixin.qq.com/sns/jscode2session"

    async def code_to_session(self, code: str) -> Optional[dict]:
        """
        使用 code 换取 openid 和 session_key

        Args:
            code: 微信登录临时凭证

        Returns:
            包含 openid 和 session_key 的字典，失败返回 None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.session_url,
                    params={
                        "appid": self.app_id,
                        "secret": self.app_secret,
                        "js_code": code,
                        "grant_type": "authorization_code"
                    },
                    timeout=10.0
                )

                data = response.json()

                # 检查是否有错误
                if "errcode" in data:
                    logger.error(f"微信 API 错误: {data.get('errmsg')}")
                    return None

                # 返回 openid 和 session_key
                return {
                    "openid": data.get("openid"),
                    "session_key": data.get("session_key"),
                    "unionid": data.get("unionid")  # 可选
                }

        except Exception as e:
            logger.error(f"调用微信 API 失败: {str(e)}")
            return None
