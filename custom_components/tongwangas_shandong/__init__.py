"""山东港华燃气集成 — 费用、余额、用气数据查询。

每个户号（subsId）作为一个 HA 设备，包含 7 个传感器实体。
token 同时保存在 config entry data 和 .storage 本地文件中，确保重启不丢失。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AuthError, TongwangasShandongApi
from .config_flow import _async_load_token_file, _async_save_token_file
from .frontend import async_register_frontend
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


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """组件级初始化：注册前端静态路径并自动登记配套卡片资源。

    放在 async_setup（而非 async_setup_entry）是因为静态路径只能注册一次，
    而配置条目可以有多个；同时这个钩子只在集成被实际加载时触发，所以不会
    给「装了但没配置」的用户平白加载前端资源。

    卡片资源注册失败不会中断集成，仅记录日志。
    """
    await async_register_frontend(hass)
    return True


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
        subs_code = subs_info.get("subsCode", subs_id)

        coordinator = _create_coordinator(
            hass, api, entry, org_id, subs_id, subs_code, subs_info, scan_interval,
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


async def _fetch_daily_gas_statistics(
    hass: HomeAssistant, gas_total_entity_id: str, days: int = 730,
) -> tuple[float | None, list[dict[str, Any]]]:
    """读取累计用气量(gas_total)实体的 sum 统计量，得到每日用气量序列。

    利用 HA 为 total_increasing 实体自动生成的长期统计表（statistics）。按官方定义，
    ``sum`` 是「自首次统计以来的累计增量」（单调不减，等价于表读数减基准值），
    **不是**当天用量，因此需要把相邻两天的 ``sum`` 相减才是每日用气量。

    为兼容不同 HA 版本的聚合实现（有的可能直接返回当期增量），这里自动判断：
    ``sum`` 序列单调不减即视为累计值做差分，否则视为当期值直接采用。

    返回 ``(last_day_sum, graph)``，其中 ``graph`` 为
    ``[{"date": "YYYY-MM-DD", "gasSum": float}, ...]``（仅包含有消耗的天）。
    若 recorder 未启用、实体尚不存在或无数据，则返回 ``(None, [])``。
    """
    try:
        from functools import partial
        from inspect import signature

        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder import statistics as _rec_stats
    except Exception:  # noqa: BLE001 - recorder 可能未安装
        return None, []

    # 关键：要用 statistics_during_period（复数）。它接收一组 statistic_ids + period，
    # 返回 {statistic_id: [每期 Statistics, ...]}，正是“按天序列”所需。
    # statistic_during_period（单数）返回的是整段的单个聚合统计，拿不到按天序列，
    # 之前误用了它，才接连报 statistic_ids / period / types 参数错误。
    # 这里优先复数版，个别版本缺失时兜底单数版。
    _fn = getattr(_rec_stats, "statistics_during_period", None)
    if _fn is None:
        _fn = getattr(_rec_stats, "statistic_during_period", None)
    if _fn is None:
        _LOGGER.debug("未找到 statistics_during_period，跳过每日用气量")
        return None, []

    # 仅传签名里确实存在的参数，兼顾不同版本参数名/个数的差异。
    _params = signature(_fn).parameters
    _call_kwargs: dict[str, Any] = {}
    if "statistic_ids" in _params:
        _call_kwargs["statistic_ids"] = {gas_total_entity_id}
    elif "statistic_id" in _params:
        _call_kwargs["statistic_id"] = gas_total_entity_id
    if "period" in _params:
        _call_kwargs["period"] = "day"
    if "units" in _params:
        _call_kwargs["units"] = None
    if "types" in _params:
        # 注意：HA 源码里 types 的类型是 set[Literal[...]]（**不是** Optional，也没有默认值），
        # 函数内部第一件事就是 `for stat_type in _types:`。传 None 会直接抛
        # TypeError: 'NoneType' object is not iterable —— 这正是上一轮报错的原因。
        # "sum" 取 total_increasing 的累计增量；"state" 作为兜底（万一只返回 state 列）。
        _call_kwargs["types"] = {"state", "sum"}
    _LOGGER.debug("统计量查询：fn=%s 参数=%s", _fn.__name__, _call_kwargs)

    end_time = dt_util.now()
    start_time = end_time - timedelta(days=days)
    try:
        stats = await get_instance(hass).async_add_executor_job(
            partial(_fn, hass, start_time, end_time, **_call_kwargs)
        )
    except Exception as err:  # noqa: BLE001 - 统计表查询失败不应影响主流程
        _LOGGER.debug("读取用气每日统计量失败（recorder 可能未启用）: %s", err)
        return None, []

    # 归一化返回：dict[statistic_id, list] / list / 单个 Statistics
    if isinstance(stats, dict):
        rows = stats.get(gas_total_entity_id)
        if rows is None and stats:
            rows = next(iter(stats.values()))
    elif isinstance(stats, list):
        rows = stats
    elif stats is None:
        rows = None
    else:
        rows = [stats]
    _LOGGER.debug(
        "每日用气量统计查询：实体=%s 命中行数=%s",
        gas_total_entity_id,
        len(rows) if rows else 0,
    )
    if not rows:
        return None, []

    local_tz = dt_util.get_default_time_zone()

    # HA 返回的行是**普通 dict**（StatisticsRow 只是 TypedDict，用于类型标注），
    # 键为 start / end / mean / min / max / last_reset / state / sum。
    # 关键：**start 是 Unix 时间戳 float**（源码 `class BaseStatisticsRow: start: float`；
    # 日统计的 start 来自 `_day_start_end_ts()` 的 `start_local.timestamp()`），
    # **不是 datetime** —— 直接对它调用 .astimezone() 会抛 AttributeError。
    def _row_get(row: Any, key: str) -> Any:
        """兼容 dict / 具名元组 / dataclass / SQLAlchemy Row 等多种返回形态。"""
        if isinstance(row, dict):
            return row.get(key)
        # SQLAlchemy Row 等：用 _mapping 按列名取
        mapping = getattr(row, "_mapping", None)
        if mapping is not None:
            try:
                return mapping.get(key)
            except Exception:  # noqa: BLE001
                pass
        return getattr(row, key, None)

    def _to_utc_dt(value: Any) -> datetime | None:
        """把统计量的 start 归一化为带时区的 datetime。

        支持 Unix 时间戳（HA 实际返回的形态，秒/毫秒均可）、datetime、ISO 字符串。
        """
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e11:  # 毫秒时间戳
                ts /= 1000.0
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    def _to_float(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    _LOGGER.debug("统计量首行样例：%s", repr(rows[0])[:300])

    # 先收集 (start 时间, 本地日期, sum 值, state 值)。
    # period="day" 时每行即一天；若某版本返回小时级原始统计，则同日只保留最晚一条
    # （即当日结束时的累计值），后续差分逻辑对两者都成立。
    _collected: list[tuple[datetime, str, float | None, float | None]] = []
    _bad_start = 0
    for row in rows:
        start_dt = _to_utc_dt(_row_get(row, "start"))
        if start_dt is None:
            _bad_start += 1
            continue
        # HA 的日统计按**本地日**切分，换算回本地时区即是“当天”
        date_str = start_dt.astimezone(local_tz).strftime("%Y-%m-%d")
        # sum / sum_increase 是 total_increasing 的累计增量；state 是累计表读数（兜底）
        sum_value = _to_float(_row_get(row, "sum"))
        if sum_value is None:
            sum_value = _to_float(_row_get(row, "sum_increase"))
        state_value = _to_float(_row_get(row, "state"))
        if sum_value is None and state_value is None:
            continue
        _collected.append((start_dt, date_str, sum_value, state_value))

    if not _collected:
        _LOGGER.debug(
            "每日用气量统计解析：%d 行全部丢弃（start 非法 %d 行，数值全空 %d 行），首行=%s",
            len(rows),
            _bad_start,
            len(rows) - _bad_start,
            repr(rows[0])[:300],
        )
        return None, []

    _collected.sort(key=lambda item: item[0])
    _by_date: dict[str, tuple[float | None, float | None]] = {}
    for _start, date_str, sum_value, state_value in _collected:
        # 时间升序写入，最后命中即当天最晚的一条（当日累计值）
        prev = _by_date.get(date_str)
        # 同一天内逐项补齐缺失列，避免晚出现的行把已有列覆盖成 None
        merged = (
            sum_value if sum_value is not None else (prev[0] if prev else None),
            state_value if state_value is not None else (prev[1] if prev else None),
        )
        _by_date[date_str] = merged

    # 选定使用哪一列：优先 sum；若 sum 全为 0/缺失（例如实体刚获得 state_class、
    # 统计量尚未累计），则退回 state（累计表读数）。
    _sum_series = [(d, v[0]) for d, v in sorted(_by_date.items()) if v[0] is not None]
    _state_series = [(d, v[1]) for d, v in sorted(_by_date.items()) if v[1] is not None]
    _sum_has_data = len(_sum_series) > 1 and max(v for _, v in _sum_series) > 0
    raw_series: list[tuple[str, float]] = _sum_series if _sum_has_data else _state_series
    _LOGGER.debug(
        "每日用气量统计原始值（列=%s, 前3/后3）：%s ... %s",
        "sum" if _sum_has_data else "state",
        raw_series[:3],
        raw_series[-3:],
    )
    if len(raw_series) < 2:
        return None, []

    # 判断 sum 是「累计值」还是「当期值」：
    #   累计值（HA 对 total_increasing 的默认语义）：单调不减 → 差分得到每次跳表的增量
    #   当期值：随日期上下波动 → 直接采用
    _vals = [value for _, value in raw_series]
    _non_decreasing = sum(
        1 for i in range(1, len(_vals)) if _vals[i] >= _vals[i - 1] - 1e-9
    )
    _rise_ratio = _non_decreasing / (len(_vals) - 1) if len(_vals) > 1 else 0.0
    _is_cumulative = max(_vals) > min(_vals) and _rise_ratio >= 0.9

    if not _is_cumulative:
        # 已是当期增量：直接采用（仅保留有消耗的日子）
        graph: list[dict[str, Any]] = [
            {"date": d, "gasSum": round(v, 3)} for d, v in raw_series if v > 0
        ]
        if not graph:
            return None, []
        return graph[-1]["gasSum"], graph

    # ---- 累计值：差分出「每次跳表的增量」，再把增量平摊回距上次跳表的每一天 ----
    # 背景：家用燃气表精度为 1 m³（gas_total 读数均为整数），真实日用量常不足 1 m³，
    # 于是表具要攒够 1 m³ 才跳一次表 —— 表现为「某几天没有数据，某天突然 +1」。
    # 此时若把没有数据的天空着、或记 0，都会谎报「当天零消耗」；
    # 平摊到距上次跳表的每一天，既不产生虚假尖峰，又**保证总量不变**
    # （任意区间的合计仍等于表具累计读数的实际增量，月账单口径不受影响）。
    #
    # 只统计「完整日」（截至昨天）：今天还没结束、读数不完整，且跳表常发生在凌晨
    # （实际是前一晚的用量），把当天计入会得到一个虚高且当天内不断变化的值。
    today = dt_util.now().astimezone(local_tz).date()
    yesterday = today - timedelta(days=1)

    def _as_date(date_str: str) -> date:
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    daily: dict[str, float] = {}
    prev_tick = _as_date(raw_series[0][0])
    _deferred = 0.0
    for i in range(1, len(raw_series)):
        date_str, value = raw_series[i]
        delta = value - _vals[i - 1]
        if delta < 0:
            # 换表 / 读数重置：不产生用量，但把基准日期推进
            prev_tick = _as_date(date_str)
            continue
        if delta == 0:
            continue
        tick_date = _as_date(date_str)
        end_date = min(tick_date, yesterday)
        span = (end_date - prev_tick).days
        if span < 1:
            # 增量落在今天、且上次跳表也在昨天/今天 → 暂无可归属的完整日，
            # 先搁置；下次刷新（今天变成完整日）时会重新计算并正确归属。
            _deferred += delta
            prev_tick = tick_date
            continue
        per_day = delta / span
        for k in range(1, span + 1):
            day_key = (prev_tick + timedelta(days=k)).strftime("%Y-%m-%d")
            daily[day_key] = daily.get(day_key, 0.0) + per_day
        prev_tick = tick_date

    # 最后一次跳表之后直到昨天：表具始终没有跳表 → 记 0（确实未观测到消耗）
    cursor = min(prev_tick, yesterday) + timedelta(days=1)
    while cursor <= yesterday:
        daily.setdefault(cursor.strftime("%Y-%m-%d"), 0.0)
        cursor += timedelta(days=1)

    graph = [{"date": d, "gasSum": round(v, 3)} for d, v in sorted(daily.items())]
    if not graph:
        return None, []
    _LOGGER.debug(
        "每日用气量：共 %d 天（%s ~ %s），合计 %.3f m³；未归属(今天)增量 %.3f；末3天=%s",
        len(graph),
        graph[0]["date"],
        graph[-1]["date"],
        sum(row["gasSum"] for row in graph),
        _deferred,
        graph[-3:],
    )
    return graph[-1]["gasSum"], graph


async def _async_load_daily_cache(
    hass: HomeAssistant, subs_code: str,
) -> dict[str, float]:
    """从 .storage 加载已缓存的每日用气量（日期->气量）。"""
    store = Store(hass, 1, f"{DOMAIN}/daily_{subs_code}")
    data = await store.async_load()
    if isinstance(data, dict) and isinstance(data.get("graph"), dict):
        return data["graph"]
    return {}


async def _async_save_daily_cache(
    hass: HomeAssistant, subs_code: str, mapping: dict[str, float],
) -> None:
    """将每日用气量序列落本地 .storage，重启不丢失、每次更新再同步。"""
    store = Store(hass, 1, f"{DOMAIN}/daily_{subs_code}")
    await store.async_save({"graph": mapping})


def _create_coordinator(
    hass: HomeAssistant,
    api: TongwangasShandongApi,
    entry: ConfigEntry,
    org_id: str,
    subs_id: str,
    subs_code: str,
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


        # 每日用气量：优先从 HA 统计量（gas_total 的 sum）读取，查到后落本地缓存，
        # 每次更新再与缓存合并同步，保证历史不丢、且对 recorder 波动有兜底。
        # 实体 id 以 subsCode 拼接（与 sensor.py 中 entity_id 一致）。
        try:
            cache_map = await _async_load_daily_cache(hass, subs_code)
            fresh_last, fresh_graph = await _fetch_daily_gas_statistics(
                hass, f"sensor.{DOMAIN}_gas_total_{subs_code}", days=730,
            )
            fresh_map = {row["date"]: row["gasSum"] for row in fresh_graph}
            # 合并：最新查询优先，缓存补缺；限制保留最近 730 天
            merged = {**cache_map, **fresh_map}
            # 只保留「完整日」（今天不统计：当天读数不完整，且跳表常发生在凌晨）。
            # 同时清掉缓存里可能残留的今天/未来日期，避免 state 又变回当天的值。
            today_key = dt_util.now().strftime("%Y-%m-%d")
            merged = {d: v for d, v in merged.items() if d < today_key}
            if len(merged) > 730:
                for old_key in sorted(merged.keys())[:-730]:
                    merged.pop(old_key, None)
            await _async_save_daily_cache(hass, subs_code, merged)
            daily_graph = [
                {"date": d, "gasSum": merged[d]} for d in sorted(merged.keys())
            ]
            daily_last = daily_graph[-1]["gasSum"] if daily_graph else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("获取每日用气量失败，回退本地缓存: %s", err)
            cache_map = await _async_load_daily_cache(hass, subs_code)
            today_key = dt_util.now().strftime("%Y-%m-%d")
            daily_graph = [
                {"date": d, "gasSum": cache_map[d]}
                for d in sorted(cache_map.keys())
                if d < today_key
            ]
            daily_last = daily_graph[-1]["gasSum"] if daily_graph else None

        result["gas_total_daily"] = daily_last
        result["gas_total_daily_graph"] = daily_graph

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
