"""山东港华燃气集成 — 费用、余额、用气数据查询。

每个户号（subsId）作为一个 HA 设备，包含 7 个传感器实体。
token 同时保存在 config entry data 和 .storage 本地文件中，确保重启不丢失。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AuthError, TongwangasShandongApi
from .config_flow import _async_load_token_file, _async_save_token_file
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_MOBILE,
    CONF_ORG_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SIGN,
    CONF_SUBS,
    CONF_TOKEN_CREATE_TIME,
    CONF_TOKEN_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TOKEN_REFRESH_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

type TongwangasShandongConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: TongwangasShandongConfigEntry,
) -> bool:
    """设置山东港华燃气集成。"""
    data = entry.data
    host = data.get(CONF_HOST, "")
    org_id = data.get(CONF_ORG_ID, "")
    mobile = data.get(CONF_MOBILE, "")

    # 尝试从本地文件恢复 token（优先使用 config entry 中的值）
    access_token = data.get(CONF_ACCESS_TOKEN, "")
    refresh_token = data.get(CONF_REFRESH_TOKEN, "")
    token_create_time = data.get(CONF_TOKEN_CREATE_TIME, 0)

    # 如果 config entry 中没有 token，尝试从本地文件加载
    if (not access_token or not refresh_token) and mobile:
        file_data = await _async_load_token_file(hass, mobile)
        if file_data:
            access_token = access_token or file_data.get(CONF_ACCESS_TOKEN, "")
            refresh_token = refresh_token or file_data.get(CONF_REFRESH_TOKEN, "")
            token_create_time = token_create_time or file_data.get(
                CONF_TOKEN_CREATE_TIME, 0,
            )

    session = async_get_clientsession(hass, verify_ssl=False)

    # 创建 API 客户端
    api = TongwangasShandongApi(
        session=session,
        host=host,
        access_token=access_token,
        refresh_token=refresh_token,
        sign=data.get(CONF_SIGN, ""),
        token_create_time=token_create_time,
    )

    # 获取刷新间隔配置
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    token_refresh_interval = entry.options.get(
        CONF_TOKEN_REFRESH_INTERVAL,
        entry.data.get(CONF_TOKEN_REFRESH_INTERVAL, DEFAULT_TOKEN_REFRESH_INTERVAL),
    )

    # 为每个户号创建独立的 coordinator
    subs_list: list[dict[str, Any]] = data.get(CONF_SUBS, [])
    coordinators: dict[str, DataUpdateCoordinator] = {}

    for subs_info in subs_list:
        subs_id = subs_info.get("subsId", "")
        if not subs_id:
            continue

        coordinator = _create_coordinator(
            hass, api, entry, org_id, subs_id, subs_info, scan_interval,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[subs_id] = coordinator

    # ------------------------------------------------------------------
    #  Token 定时刷新（独立于数据刷新）
    # ------------------------------------------------------------------

    def _schedule_token_refresh(delay: float) -> None:
        """安排下一次 token 刷新。"""
        entry.async_on_unload(async_call_later(hass, delay, _token_refresh_job))

    async def _token_refresh_job(_now=None) -> None:
        """定时刷新 token，成功后持久化，失败则触发重新认证。"""
        try:
            if await api.refresh_access_token():
                # 刷新成功，保存 token
                _persist_tokens(hass, entry, api)
                if mobile:
                    await _async_save_token_file(
                        hass, mobile,
                        api.access_token, api.refresh_token,
                        api.token_create_time,
                    )
                _LOGGER.debug("定时 token 刷新成功, remain=%ss", api.bearer_remain)
            else:
                _LOGGER.warning("定时 token 刷新失败（网络问题），将在下次尝试")
        except AuthError as err:
            _LOGGER.warning("定时 token 刷新永久失败，需要重新配置: %s", err)
            entry.async_start_reauth(hass)
            return  # 不再安排下次刷新
        _schedule_token_refresh(token_refresh_interval)

    # 首次 token 刷新：取配置间隔和剩余有效时间的较小值
    _first_delay = min(
        token_refresh_interval, max(api.bearer_remain - 60, 60),
    )
    _schedule_token_refresh(_first_delay)

    # 保存到 hass.data 供 sensor / button 平台使用
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _create_coordinator(
    hass: HomeAssistant,
    api: TongwangasShandongApi,
    entry: ConfigEntry,
    org_id: str,
    subs_id: str,
    subs_info: dict[str, Any],
    scan_interval: int,
) -> DataUpdateCoordinator:
    """为单个户号创建 DataUpdateCoordinator。

    每次更新调用 3 个接口：gasFeeBaseinfo、gasConsumptionDataQuery、gasStepFee，
    合并结果后返回供传感器使用。
    """
    # 标记是否已触发 reauth，避免重复触发
    _reauth_triggered = False
    # 缓存上次成功的数据，reauth 时返回以保持实体状态
    _last_data: dict[str, Any] = {}

    async def _update() -> dict[str, Any]:
        """拉取该户号的全部传感器数据。"""
        nonlocal _reauth_triggered, _last_data

        #_LOGGER.debug("coordinator 更新 — subs_id=%s token_remain=%ss bearer_valid=%s",subs_id, api.bearer_remain, api.bearer_valid,)

        # 安全网：如果 token 已过期，先尝试刷新
        if not api.bearer_valid:
            try:
                if not await api.refresh_access_token():
                    _LOGGER.warning("token 刷新失败（网络问题），继续使用当前 token")
            except AuthError as err:
                # refreshToken 失效，触发 reauth 但保持实体数据不变
                if not _reauth_triggered:
                    _LOGGER.warning("refreshToken 失效，触发重新认证: %s", err)
                    entry.async_start_reauth(hass)
                    _reauth_triggered = True
                # 返回上次缓存数据，实体保持当前状态
                return _last_data

        try:
            # 并发调用 4 个接口（无依赖关系）
            fee_info, consumption_data, step_fee, charge_precheck = await asyncio.gather(
                api.get_gas_fee_baseinfo(org_id, subs_id),
                api.get_gas_consumption_data(subs_id),
                api.get_gas_step_fee(org_id, subs_id),
                api.charge_precheck(org_id, subs_id),
                return_exceptions=True,
            )
        except Exception as err:
            raise UpdateFailed(f"API 请求失败: {err}") from err

        # 检查各接口返回是否有效
        result: dict[str, Any] = {"subsId": subs_id}

        # 费用信息
        if isinstance(fee_info, dict) and fee_info.get("resultCode") == "0":
            result["feePayable"] = fee_info.get("feePayable")
            result["availableBalance"] = fee_info.get("availableBalance")
            result["lastMeterReadingDate"] = fee_info.get("lastMeterReadingDate")
        elif isinstance(fee_info, AuthError):
            # refreshToken 失效，触发 reauth 但保持实体数据不变
            if not _reauth_triggered:
                _LOGGER.warning("refreshToken 失效，触发重新认证: %s", fee_info)
                entry.async_start_reauth(hass)
                _reauth_triggered = True
            return _last_data
        elif isinstance(fee_info, Exception):
            _LOGGER.warning("gasFeeBaseinfo 请求失败: %s", fee_info)

        # 用气记录
        if isinstance(consumption_data, dict) and consumption_data.get("resultCode") == "0":
            result["gasConsumptionTrendInfo"] = consumption_data.get(
                "gasConsumptionTrendInfo", [],
            )
            result["gasConsumptionInfo"] = consumption_data.get(
                "gasConsumptionInfo", [],
            )
        elif isinstance(consumption_data, AuthError):
            if not _reauth_triggered:
                _LOGGER.warning("refreshToken 失效，触发重新认证: %s", consumption_data)
                entry.async_start_reauth(hass)
                _reauth_triggered = True
            return _last_data
        elif isinstance(consumption_data, Exception):
            _LOGGER.warning("gasConsumptionDataQuery 请求失败: %s", consumption_data)

        # 阶梯气价
        if isinstance(step_fee, dict) and step_fee.get("resultCode") == "0":
            datas = step_fee.get("datas", {})
            if isinstance(datas, dict):
                # buyamount = datas.get("buyamount")
                gas_total_yearly = float(datas.get("buyamount", 0))
                step_list = datas.get("stepList", [])

                current_step = None
                for step in step_list:
                    max_mount = step.get("maxMount")
                    if max_mount is None:
                        continue
                    max_mount = float(max_mount)
                    if max_mount == -1 or gas_total_yearly <= max_mount:
                        current_step = step
                        break
                if current_step:
                    _LOGGER.debug("命中阶梯：%s", current_step["stepName"])
                    _LOGGER.debug("对应价格：%s", current_step["price"])
                    result["step_name"] = current_step["stepName"]
                    result["step_list"] = step_list

                result["gas_total_yearly"] = gas_total_yearly
        elif isinstance(step_fee, AuthError):
            if not _reauth_triggered:
                _LOGGER.warning("refreshToken 失效，触发重新认证: %s", step_fee)
                entry.async_start_reauth(hass)
                _reauth_triggered = True
            return _last_data
        elif isinstance(step_fee, Exception):
            _LOGGER.warning("gasStepFee 请求失败: %s", step_fee)

        # 缴费预检查接口
        if isinstance(charge_precheck, dict) and charge_precheck.get("resultCode") == "0":
            datas = charge_precheck.get("datas", {})
            if isinstance(datas, dict) :
                readingRptList = datas.get("readingRptList", [])
                maxReading = 0
                for reading in readingRptList:
                    if float(reading["currReading"]) > maxReading:
                        maxReading = float(reading["currReading"])
                _LOGGER.debug("当前表读数：%s", maxReading)
                if maxReading > 0:
                    result["gas_total"] = maxReading
                else:
                    result["gas_total"] = _last_data.get("gas_total", 0)
        elif isinstance(charge_precheck, AuthError):
            if not _reauth_triggered:
                _LOGGER.warning("refreshToken 失效，触发重新认证: %s", charge_precheck)
                entry.async_start_reauth(hass)
                _reauth_triggered = True
            return _last_data
        elif isinstance(charge_precheck, Exception):
            _LOGGER.warning("gasConsumptionDataQuery 请求失败: %s", charge_precheck)


        # 持久化 token（刷新后的新 token 写回 config entry）
        _persist_tokens(hass, entry, api)

        # 缓存本次成功的数据，供 reauth 时返回
        _last_data = result
        return result

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"tongwangas_shandong_{subs_id[:8]}",
        update_method=_update,
        update_interval=timedelta(seconds=scan_interval),
    )


def _persist_tokens(
    hass: HomeAssistant, entry: ConfigEntry, api: TongwangasShandongApi,
) -> None:
    """将刷新后的 token 写回 config entry data，确保重启后可用。"""
    new_data = {**entry.data}
    changed = False
    for key, val in (
        (CONF_ACCESS_TOKEN, api.access_token),
        (CONF_REFRESH_TOKEN, api.refresh_token),
        (CONF_TOKEN_CREATE_TIME, api.token_create_time),
    ):
        if new_data.get(key) != val:
            new_data[key] = val
            changed = True
    if changed:
        hass.config_entries.async_update_entry(entry, data=new_data)


async def async_unload_entry(
    hass: HomeAssistant, entry: TongwangasShandongConfigEntry,
) -> bool:
    """卸载 config entry。"""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok
