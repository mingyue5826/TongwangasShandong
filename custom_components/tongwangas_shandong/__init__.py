"""The 山东港华燃气 integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

DOMAIN = "tongwangas_shandong"
PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class TongwangasCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """自定义数据更新协调器（严格对齐 request.md 规范）."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """初始化 Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        """发起符合 request.md 规范的 GET 请求."""
        host = self.entry.data.get("host", "").rstrip("/")
        org_id = self.entry.data.get("org_id", "")
        access_token = self.entry.data.get("access_token", "")
        refresh_token = self.entry.data.get("refresh_token", "")
        sign = self.entry.data.get("sign", "")

        # 拼接基础 URL
        if not host.startswith("http://") and not host.startswith("https://"):
            url = f"https://{host}/api/v1/gas/balance"  # TODO: 若相对路径不同，请在此修改
        else:
            url = f"{host}/api/v1/gas/balance"

        # 1. Header 仅保留 Authorization 认证头
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        }

        # 2. 将凭证与签名作为 URL Query Parameters (requestParam)
        params = {
            "access-token": access_token or "",
            "refresh-token": refresh_token or "",
            "sign": sign or "",
            "org_id": org_id or "",
        }

        _LOGGER.debug(
            "[GET Request] 正在请求 -> URL: %s\nHeaders: %s\nParams: %s",
            url,
            headers,
            params,
        )

        try:
            # 传入 params 参数，aiohttp 会自动将其拼接到 URL 查询串后
            async with self.session.get(url, headers=headers, params=params, timeout=15) as response:
                status_code = response.status
                response_text = await response.text()

                _LOGGER.debug(
                    "[GET Response] HTTP Code: %s\nResponse Body: %s",
                    status_code,
                    response_text,
                )

                if status_code != 200:
                    raise UpdateFailed(
                        f"HTTP 请求失败, 状态码: {status_code}, 返回: {response_text}"
                    )

                res_json = await response.json()
                data = res_json.get("data", {})
                if not isinstance(data, dict):
                    data = {"raw_response": res_json}

                return data

        except Exception as err:
            _LOGGER.error("从港华燃气 API 获取数据时发生错误: %s", err, exc_info=True)
            raise UpdateFailed(f"网络请求异常: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从 ConfigEntry 加载并初始化组件."""
    hass.data.setdefault(DOMAIN, {})

    org_id = entry.data.get("org_id")
    org_name = entry.data.get("org_name")
    host = entry.data.get("host")

    _LOGGER.info(
        "初始化山东港华燃气集成: org_id=%s, org_name=%s, host=%s",
        org_id,
        org_name,
        host,
    )

    coordinator = TongwangasCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "selected_subs": entry.data.get("selected_subs", []),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok