"""山东港华燃气诊断实体按钮."""

from datetime import datetime
from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """设置 Token 刷新按钮诊断实体."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api = entry_data["api"]
    selected_subs = entry.data["selected_subs"]

    # 将按钮挂载在第一个选中的户号设备下
    first_subs_id = next(iter(selected_subs.keys()))
    first_subs_info = selected_subs[first_subs_id]

    async_add_entities(
        [RefreshTokenButton(api, entry, first_subs_id, first_subs_info)]
    )


class RefreshTokenButton(ButtonEntity):
    """刷新 Token 按钮实体."""

    _attr_device_class = ButtonDeviceClass.UPDATE

    def __init__(self, api, entry: ConfigEntry, subs_id: str, subs_info: dict):
        """初始化按钮."""
        self.api = api
        self.entry = entry
        self.subs_id = subs_id
        self._attr_name = "刷新 Token"
        self._attr_unique_id = f"{entry.entry_id}_refresh_token_button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.subs_id)},
            name=subs_info.get("displayAddr", "燃气户号"),
        )
        self._last_refresh_time = entry.data.get("last_refresh_time", "从未刷新")

    @property
    def extra_state_attributes(self):
        """在属性中提供上次刷新时间."""
        return {"last_refresh_time": self._last_refresh_time}

    async def async_press(self) -> None:
        """点击按钮后立即刷新 Token."""
        success = await self.api.async_refresh_token()
        if success:
            self._last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.async_write_ha_state()