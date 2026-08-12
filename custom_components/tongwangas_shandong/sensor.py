"""山东港华燃气传感器平台。

每个户号（subsId）作为一个 HA 设备，包含 7 个传感器：
- 应缴费用 (feePayable)
- 可用余额 (availableBalance)
- 上次抄表日期 (lastMeterReadingDate)
- 今年累计用气量 (buyamount)
- 阶梯气价 (stepList) — 状态固定"正常"，attributes.graph 为阶梯列表
- 用气趋势 (gasConsumptionTrendInfo) — 状态固定"图表"，attributes.graph 为趋势数据
- 用气明细 (gasConsumptionInfo) — 状态固定"图表"，attributes.graph 为用气记录
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import UnitOfVolume
from datetime import datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import get_time_zone

from .const import (
    DOMAIN,
    CONF_SUBS,
)

_LOGGER = logging.getLogger(__name__)


# 每种传感器的配置：key、data_key、名称、图标、设备类、单位、状态类、固定状态值
_SENSOR_CONFIGS: list[dict[str, Any]] = [
    {
        "key": "fee_payable",
        "data_key": "feePayable",
        "name": "应缴费用",
        "icon": "mdi:currency-cny",
        "device_class": None,
        "unit": "元",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "available_balance",
        "data_key": "availableBalance",
        "name": "可用余额",
        "icon": "mdi:wallet",
        "device_class": None,
        "unit": "元",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "last_meter_reading_date",
        "data_key": "lastMeterReadingDate",
        "name": "上次抄表日期",
        "icon": "mdi:calendar-clock",
        "device_class": None,
        "unit": None,
        "state_class": None,
    },
    {
        "key": "buy_amount",
        "data_key": "buyamount",
        "name": "今年累计用气量",
        "icon": "mdi:cash-multiple",
        "device_class": SensorDeviceClass.GAS,
        "unit": UnitOfVolume.CUBIC_METERS,
        "state_class": SensorStateClass.TOTAL,
        # 新增：年度统计重置时间，state_class=TOTAL强制依赖
        "reset_cycle": "year"
    },
    {
        "key": "step_list",
        "data_key": "stepList",
        "name": "阶梯气价",
        "icon": "mdi:format-list-numbered",
        "device_class": None,
        "unit": None,
        "state_class": None,
        "fixed_state": "正常",  # 状态固定为"正常"
    },
    {
        "key": "gas_consumption_trend_info",
        "data_key": "gasConsumptionTrendInfo",
        "name": "用气趋势",
        "icon": "mdi:chart-line",
        "device_class": None,
        "unit": None,
        "state_class": None,
        "fixed_state": "图表",  # 状态固定为"图表"
    },
    {
        "key": "gas_consumption_info",
        "data_key": "gasConsumptionInfo",
        "name": "用气明细",
        "icon": "mdi:chart-bar",
        "device_class": None,
        "unit": None,
        "state_class": None,
        "fixed_state": "图表",  # 状态固定为"图表"
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器平台：为每个户号创建 7 个传感器。"""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, DataUpdateCoordinator] = data["coordinators"]
    subs_list: list[dict[str, Any]] = entry.data.get(CONF_SUBS, [])

    entities: list[TongwangasShandongSensor] = []
    for subs_info in subs_list:
        subs_id = subs_info.get("subsId", "")
        coordinator = coordinators.get(subs_id)
        if not coordinator:
            continue
        # 为该户号创建 7 个传感器
        for config in _SENSOR_CONFIGS:
            entities.append(
                TongwangasShandongSensor(coordinator, subs_info, config)
            )

    async_add_entities(entities, True)


class TongwangasShandongSensor(CoordinatorEntity, SensorEntity):
    """山东港华燃气传感器实体。

    根据 sensor_config 中的 key 决定读取哪个数据字段、
    是否使用固定状态值、是否生成 YAML attributes。
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subs_info: dict[str, Any],
        sensor_config: dict[str, Any],
    ) -> None:
        """初始化传感器。"""
        super().__init__(coordinator)
        self._subs_info = subs_info
        self._config = sensor_config
        self._sensor_key = sensor_config["key"]

        subs_code = subs_info.get("subsCode", "")
        # 唯一ID和实体ID：{DOMAIN}_{sensor_key}_{subs_code}
        self._attr_unique_id = f"{DOMAIN}_{self._sensor_key}_{subs_code}"
        self._attr_name = sensor_config["name"]
        self._attr_icon = sensor_config["icon"]
        self.entity_id = f"sensor.{DOMAIN}_{self._sensor_key}_{subs_code}"

        # 设备类和单位
        if sensor_config.get("device_class"):
            self._attr_device_class = sensor_config["device_class"]
        if sensor_config.get("unit"):
            self._attr_native_unit_of_measurement = sensor_config["unit"]
        if sensor_config.get("state_class"):
            self._attr_state_class = sensor_config["state_class"]

    # ------------------------------------------------------------------
    #  设备信息（每个户号 = 一个设备）
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> dict[str, Any]:
        """设备信息：以 subsCode 为标识，displayAddr 为设备名。"""
        subs_code = self._subs_info.get("subsCode", "")
        display_addr = self._subs_info.get("displayAddr", subs_code)
        return {
            "identifiers": {(DOMAIN, subs_code)},
            "name": f"{display_addr}",
            "manufacturer": "山东港华燃气",
            "model": f"户号: {subs_code}",
            "sw_version": "1.0",
        }

    # ------------------------------------------------------------------
    #  状态值
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> Any:
        """返回传感器状态值。

        - 固定状态传感器（阶梯气价/用气趋势/用气明细）：返回固定值
        - 费用类传感器：返回 float 值
        - 日期类传感器：返回日期字符串
        """
        # 固定状态值（"正常" / "图表"）
        fixed = self._config.get("fixed_state")
        if fixed is not None:
            return fixed

        data: dict[str, Any] = self.coordinator.data or {}
        # 使用 data_key（camelCase）从 coordinator 数据中获取值
        data_key = self._config.get("data_key", self._sensor_key)
        raw = data.get(data_key)

        if raw is None:
            return None

        # 费用类传感器（单位为"元"）：转为 float
        if self._config.get("unit") == "元":
            try:
                return float(raw)
            except (ValueError, TypeError):
                return None

        # 日期类传感器：直接返回字符串
        return raw

    # 重写 last_reset 属性，默认为 None；配置中有 reset_cycle 时，返回指定周期的开始时间
    @property
    def last_reset(self) -> datetime | None:
        cycle = self._config.get("reset_cycle")
        now = datetime.now()
        local_tz = get_time_zone(self.hass.config.time_zone)
        if cycle == "year": # 年度：当年1月1日
            return datetime(now.year, 1, 1, 0, 0, tzinfo=local_tz)
        elif cycle == "month": # 月度：当月1日
            return datetime(now.year, now.month, 1, 0, 0, tzinfo=local_tz)
        elif cycle == "day": # 每日：当天0点
            return datetime(now.year, now.month, now.day, 0, 0, tzinfo=local_tz)
        return None

    # ------------------------------------------------------------------
    #  额外属性（图表类传感器，返回真实 list 数据用于 HA 生成图表）
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """返回额外属性。

        阶梯气价/用气趋势/用气明细：attributes 中包含 graph 键，值为 list。
        """
        data: dict[str, Any] = self.coordinator.data or {}
        data_key = self._config.get("data_key", self._sensor_key)

        if self._sensor_key in ("step_list", "gas_consumption_trend_info", "gas_consumption_info"):
            return {"graph": data.get(data_key, [])}

        return {}
