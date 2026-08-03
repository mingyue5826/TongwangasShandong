"""山东港华燃气按钮实体 — 刷新数据 & 刷新Token。"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AuthError, TongwangasShandongApi
from .config_flow import _async_save_token_file
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MOBILE,
    CONF_REFRESH_TOKEN,
    CONF_SUBS,
    CONF_TOKEN_CREATE_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 按钮类型键名
BUTTON_REFRESH_DATA = "refresh_data"
BUTTON_REFRESH_TOKEN = "refresh_token"

# 按钮配置：key → (name, icon, description)
BUTTON_CONFIGS: dict[str, dict[str, Any]] = {
    BUTTON_REFRESH_DATA: {
        "name": "刷新数据",
        "icon": "mdi:refresh",
    },
    BUTTON_REFRESH_TOKEN: {
        "name": "刷新Token",
        "icon": "mdi:refresh",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """为每个户号添加按钮实体。"""
    data = hass.data[DOMAIN][entry.entry_id]
    api: TongwangasShandongApi = data["api"]
    coordinators = data["coordinators"]
    subs_list: list[dict[str, Any]] = entry.data.get(CONF_SUBS, [])

    entities: list[TongwangasShandongButton] = []
    for subs_info in subs_list:
        subs_id = subs_info.get("subsId", "")
        if not subs_id:
            continue
        coordinator = coordinators.get(subs_id)
        if not coordinator:
            continue

        for key, cfg in BUTTON_CONFIGS.items():
            entities.append(
                TongwangasShandongButton(
                    api=api,
                    coordinator=coordinator,
                    hass=hass,
                    entry=entry,
                    subs_info=subs_info,
                    button_key=key,
                    button_config=cfg,
                )
            )

    async_add_entities(entities)


class TongwangasShandongButton(ButtonEntity):
    """山东港华燃气按钮实体基类。

    根据 button_key 决定按下行为：
    - refresh_data：立即刷新该户号数据
    - refresh_token：刷新 token 后刷新该户号数据
    """

    _attr_has_entity_name = True
    _attr_entity_category = None  # 诊断类别在下方设置

    def __init__(
        self,
        api: TongwangasShandongApi,
        coordinator,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subs_info: dict[str, Any],
        button_key: str,
        button_config: dict[str, Any],
    ) -> None:
        """初始化按钮。"""
        self._api = api
        self._coordinator = coordinator
        self._hass = hass
        self._entry = entry
        self._subs_info = subs_info
        self._button_key = button_key

        subs_code = subs_info.get("subsCode", "")
        # 唯一ID和实体ID：{DOMAIN}_{button_key}_{subs_code}
        self._attr_unique_id = f"{DOMAIN}_{button_key}_{subs_code}"
        self.entity_id = f"button.{DOMAIN}_{button_key}_{subs_code}"
        self._attr_name = button_config["name"]
        self._attr_icon = button_config["icon"]
        # 诊断类别
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> dict[str, Any]:
        """设备信息：与传感器共享同一设备（使用 subsCode）。"""
        subs_code = self._subs_info.get("subsCode", "")
        return {
            "identifiers": {(DOMAIN, subs_code)},
        }

    async def async_press(self) -> None:
        """按钮按下时的行为。"""
        if self._button_key == BUTTON_REFRESH_DATA:
            # 刷新数据：立即请求 coordinator 更新
            _LOGGER.info("[Button] 刷新数据: subs_code=%s", self._subs_info.get("subsCode", ""))
            await self._coordinator.async_request_refresh()

        elif self._button_key == BUTTON_REFRESH_TOKEN:
            # 刷新Token：先刷新token，再刷新数据
            _LOGGER.info("[Button] 刷新Token: subs_code=%s", self._subs_info.get("subsCode", ""))
            try:
                ok = await self._api.refresh_access_token()
                if ok:
                    # 刷新成功，持久化 token
                    mobile = self._entry.data.get(CONF_MOBILE, "")
                    if mobile:
                        await _async_save_token_file(
                            self._hass, mobile,
                            self._api.access_token,
                            self._api.refresh_token,
                            self._api.token_create_time,
                        )
                    # 更新 config entry data
                    new_data = {**self._entry.data}
                    new_data[CONF_ACCESS_TOKEN] = self._api.access_token
                    new_data[CONF_REFRESH_TOKEN] = self._api.refresh_token
                    new_data[CONF_TOKEN_CREATE_TIME] = self._api.token_create_time
                    self._hass.config_entries.async_update_entry(self._entry, data=new_data)
                    _LOGGER.info("[Button] Token 刷新成功, remain=%ss", self._api.bearer_remain)
                    # 刷新数据
                    await self._coordinator.async_request_refresh()
                else:
                    _LOGGER.warning("[Button] Token 刷新失败（接口返回非0）")
            except AuthError as err:
                _LOGGER.error("[Button] Token 刷新失败，需要重新认证: %s", err)
