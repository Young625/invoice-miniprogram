"""微信小程序服务"""
import httpx
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class WeChatService:
    """微信小程序服务"""

    def __init__(self, app_id: str, app_secret: str, service_account_id: Optional[str] = None, service_account_secret: Optional[str] = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.service_account_id = service_account_id
        self.service_account_secret = service_account_secret
        self.session_url = "https://api.weixin.qq.com/sns/jscode2session"
        self.token_url = "https://api.weixin.qq.com/cgi-bin/token"
        self.subscribe_msg_url = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
        self.template_msg_url = "https://api.weixin.qq.com/cgi-bin/message/template/send"
        self._access_token: Optional[str] = None
        self._service_access_token: Optional[str] = None

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

    async def get_access_token(self) -> Optional[str]:
        """
        获取小程序全局唯一后台接口调用凭据（access_token）

        Returns:
            access_token 或 None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.token_url,
                    params={
                        "grant_type": "client_credential",
                        "appid": self.app_id,
                        "secret": self.app_secret
                    },
                    timeout=10.0
                )

                data = response.json()

                if "errcode" in data:
                    logger.error(f"获取 access_token 失败: {data.get('errmsg')}")
                    return None

                self._access_token = data.get("access_token")
                return self._access_token

        except Exception as e:
            logger.error(f"获取 access_token 异常: {str(e)}")
            return None

    async def send_subscribe_message(
        self,
        openid: str,
        template_id: str,
        data: Dict[str, Dict[str, str]],
        page: str = "pages/index/index"
    ) -> bool:
        """
        发送订阅消息

        Args:
            openid: 用户 openid
            template_id: 订阅消息模板 ID
            data: 消息数据，格式如 {"thing1": {"value": "发票标题"}}
            page: 点击消息跳转的页面路径

        Returns:
            是否发送成功
        """
        try:
            # 获取 access_token
            access_token = await self.get_access_token()
            if not access_token:
                logger.error("无法获取 access_token")
                return False

            # 构建请求数据
            payload = {
                "touser": openid,
                "template_id": template_id,
                "page": page,
                "data": data,
                "miniprogram_state": "formal"  # 正式版
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.subscribe_msg_url}?access_token={access_token}",
                    json=payload,
                    timeout=10.0
                )

                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"订阅消息发送成功: {openid}")
                    return True
                else:
                    logger.error(f"订阅消息发送失败: {result.get('errmsg')}")
                    return False

        except Exception as e:
            logger.error(f"发送订阅消息异常: {str(e)}")
            return False

    async def get_service_access_token(self) -> Optional[str]:
        """
        获取服务号的 access_token

        Returns:
            access_token 或 None
        """
        if not self.service_account_id or not self.service_account_secret:
            logger.warning("服务号配置未设置")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.token_url,
                    params={
                        "grant_type": "client_credential",
                        "appid": self.service_account_id,
                        "secret": self.service_account_secret
                    },
                    timeout=10.0
                )

                data = response.json()

                if "errcode" in data:
                    logger.error(f"获取服务号 access_token 失败: {data.get('errmsg')}")
                    return None

                self._service_access_token = data.get("access_token")
                return self._service_access_token

        except Exception as e:
            logger.error(f"获取服务号 access_token 异常: {str(e)}")
            return None

    async def send_template_message(
        self,
        openid: str,
        template_id: str,
        data: Dict[str, Dict[str, str]],
        url: str = "",
        miniprogram: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        发送服务号模板消息

        Args:
            openid: 服务号用户 openid
            template_id: 模板消息 ID
            data: 消息数据，格式如 {"first": {"value": "您有新的发票", "color": "#173177"}}
            url: 点击消息跳转的链接
            miniprogram: 跳转小程序配置，格式如 {"appid": "xxx", "pagepath": "pages/index/index"}

        Returns:
            是否发送成功
        """
        try:
            # 获取服务号 access_token
            access_token = await self.get_service_access_token()
            if not access_token:
                logger.error("无法获取服务号 access_token")
                return False

            # 构建请求数据
            payload = {
                "touser": openid,
                "template_id": template_id,
                "data": data
            }

            # 如果配置了小程序跳转，优先使用小程序跳转
            if miniprogram:
                payload["miniprogram"] = miniprogram
            elif url:
                payload["url"] = url

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.template_msg_url}?access_token={access_token}",
                    json=payload,
                    timeout=10.0
                )

                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"模板消息发送成功: {openid}")
                    return True
                else:
                    logger.error(f"模板消息发送失败: {result.get('errmsg')}")
                    return False

        except Exception as e:
            logger.error(f"发送模板消息异常: {str(e)}")
            return False
