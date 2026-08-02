"""Sensor platform for 山东港华燃气."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

DOMAIN = "tongwangas_shandong"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置燃气 Sensor 实体."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DataUpdateCoordinator = entry_data["coordinator"]
    selected_subs = entry_data.get("selected_subs", [])

    _LOGGER.debug(
        "[DEBUG] 正在初始化 Sensor 实体, selected_subs: %s", selected_subs
    )

    entities: list[SensorEntity] = [
        TongwangasBalanceSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class TongwangasBalanceSensor(CoordinatorEntity, SensorEntity):
    """燃气余额 Sensor 实体."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """初始化 Sensor."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_name = "燃气余额"
        self._attr_unique_id = f"{entry.entry_id}_balance"
        self._attr_native_unit_of_measurement = "元"
        self._attr_icon = "mdi:fire"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float | None:
        """从 API 返回的数据中提取余额数值."""
        if self.coordinator.data and isinstance(self.coordinator.data, dict):
            # TODO: 根据港华接口返回的实际余额 Key 名称进行提取（如 "balance" 或 "gasBalance" 等）
            balance = self.coordinator.data.get("balance") or self.coordinator.data.get("gasBalance")
            if balance is not None:
                try:
                    return float(balance)
                except ValueError:
                    return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """将完整响应附加到实体的 Attribute 中方便调试."""
        if self.coordinator.data and isinstance(self.coordinator.data, dict):
            return {
                "机构名称": self._entry.data.get("org_name"),
                "机构ID": self._entry.data.get("org_id"),
                "API原始响应": str(self.coordinator.data),
            }
        return {}