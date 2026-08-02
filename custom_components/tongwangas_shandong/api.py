"""山东港华燃气 API 请求处理模块."""

import logging
import time
from typing import Any, Dict, Optional
import aiohttp

from .const import (
    BASE_URL,
    URL_GAS_CONSUMPTION,
    URL_GAS_FEE_BASE,
    URL_GAS_STEP_FEE,
    URL_GET_USER_INFO,
    URL_QUERY_BIND_LIST,
    URL_REFRESH_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


class ShandongTowngasAPI:
    """封装与山东港华小程序后台通信的 API 客户端."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        sign: str,
        token_created_at: Optional[float] = None,
        on_token_refreshed_callback=None,
    ) -> None:
        """初始化 API 客户端."""
        self.session = session
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.sign = sign
        self.token_created_at = token_created_at or time.time()
        # Token 刷新成功后的回调函数，用于写回 HA 和本地 Store 文件
        self.on_token_refreshed_callback = on_token_refreshed_callback

    def _get_timestamp(self) -> str:
        """生成 13 位毫秒级时间戳."""
        return str(int(time.time() * 1000))

    def _get_headers(self) -> Dict[str, str]:
        """构造统一的请求 Header Header."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                "MicroMessenger/8.0.30 NetType/WIFI Language/zh_CN"
            ),
        }

    async def async_refresh_token(self) -> bool:
        """调用接口重新获取 refreshToken 与 accessToken."""
        url = f"{BASE_URL}{URL_REFRESH_TOKEN}"
        params = {
            "timestamp": self._get_timestamp(),
            "refreshToken": self.refresh_token,
            "sign": self.sign,
        }

        try:
            _LOGGER.debug("正在尝试刷新山东港华 Token...")
            async with self.session.get(
                url, params=params, headers=self._get_headers(), timeout=10
            ) as resp:
                data = await resp.json()
                if resp.status == 200 and "access_token" in data:
                    self.access_token = data["access_token"]
                    self.refresh_token = data["refresh_token"]
                    self.token_created_at = time.time()
                    _LOGGER.info("山东港华 Token 刷新成功！")

                    # 如果注册了回调，通知外部更新持久化存储
                    if self.on_token_refreshed_callback:
                        await self.on_token_refreshed_callback(
                            self.access_token,
                            self.refresh_token,
                            self.token_created_at,
                        )
                    return True
                _LOGGER.error("刷新 Token 失败，服务器返回: %s", data)
        except Exception as err:
            _LOGGER.error("请求刷新 Token 发生异常: %s", err)

        return False

    async def _request(
        self, method: str, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """统一发送 HTTP 请求逻辑，自动判断并刷新 Token."""
        # 1. 检查本地 token 产生时间是否超过 90 分钟 (5400秒)，接近 7200 秒前自动主动刷新
        if time.time() - self.token_created_at > 5400:
            _LOGGER.info("本地 Token 接近 2 小时，主动触发 Token 刷新")
            await self.async_refresh_token()

        full_url = f"{BASE_URL}{url}"
        if params is None:
            params = {}

        # 默认拼接通用参数
        params.setdefault("timestamp", self._get_timestamp())
        params.setdefault("sign", self.sign)

        for attempt in range(2):
            try:
                async with self.session.request(
                    method,
                    full_url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=10,
                ) as resp:
                    data = await resp.json()

                    # 2. 判断服务端返回代码，若 Token 过期触发被动刷新并重试
                    result_code = str(data.get("resultCode", ""))
                    if result_code == "20001" and attempt == 0:
                        _LOGGER.warning("服务端提示 Access Token 已过期，执行刷新并重试")
                        refresh_ok = await self.async_refresh_token()
                        if refresh_ok:
                            continue  # 循环重试第二次请求
                        raise Exception("Token 过期且自动刷新失败")

                    if result_code != "0":
                        raise Exception(
                            f"接口请求失败 resultCode: {result_code}, msg: {data.get('resultMsg')}"
                        )

                    return data
            except Exception as err:
                if attempt == 1:
                    raise err

        raise Exception("接口请求失败")

    async def async_get_login_user_info(self) -> Dict[str, Any]:
        """获取登录用户信息 (getLoginUserInfo)."""
        return await self._request("GET", URL_GET_USER_INFO)

    async def async_query_bind_list(self, org_id: str) -> Dict[str, Any]:
        """查询绑定户号列表 (queryBindList)."""
        params = {"isPay": "N", "orgId": org_id}
        return await self._request("GET", URL_QUERY_BIND_LIST, params=params)

    async def async_get_gas_fee_base_info(
        self, org_id: str, subs_id: str
    ) -> Dict[str, Any]:
        """获取费用基本信息 (gasFeeBaseinfo)."""
        params = {"orgId": org_id, "subsId": subs_id}
        return await self._request("GET", URL_GAS_FEE_BASE, params=params)

    async def async_get_gas_consumption_data(self, subs_id: str) -> Dict[str, Any]:
        """获取用气记录数据 (gasConsumptionDataQuery)."""
        params = {"subsId": subs_id}
        return await self._request("GET", URL_GAS_CONSUMPTION, params=params)

    async def async_get_gas_step_fee(
        self, org_id: str, subs_id: str
    ) -> Dict[str, Any]:
        """查询阶梯气价 (gasStepFee)."""
        params = {"orgId": org_id, "subsId": subs_id}
        return await self._request("GET", URL_GAS_STEP_FEE, params=params)