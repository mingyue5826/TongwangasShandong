"""前端资源注册 —— 让配套 Lovelace 卡片免手动添加资源即可使用。

本仓库是以「集成（Integration）」类别安装的，HACS 只会为「插件 / 仪表盘」类别的
仓库自动登记 Lovelace 资源，对「集成」类别不会代劳，所以必须由集成自己在后端完成
两件事（参考同为「集成 + 内置卡片」的 AlexxIT/WebRTC 的 utils.init_resource 做法）：

1. 把集成自带的 ``www/`` 目录暴露成可访问的 URL。
   官方指定的唯一方式是 ``hass.http.async_register_static_paths``（旧的
   ``hass.http.register_static_path`` 已在 HA 2025.7 移除）。静态路径挂在集成
   自有前缀下，不使用 ``/local``（那是用户 config/www 的地盘），也不与 HACS 的
   ``/hacsfiles`` 冲突。

2. 把卡片 JS 登记为 Lovelace 资源。按资源集合类型分流：

   - **storage 模式（默认）**：直接写入仪表盘资源表，效果等同于用户自己到
     「设置 → 仪表盘 → 资源」手点一次。优点是按需加载、用户可见可管理，
     且 Cast（Chromecast / Nest Hub）设备也能加载卡片。
   - **yaml 模式**：资源由用户的 ``configuration.yaml`` 定义，写不进去，
     退回 ``frontend.add_extra_js_url()`` 全局注入（与 ``frontend.extra_module_url``
     同款机制）。代价是所有面板都会加载该 JS，且 Cast 设备不加载 extra module。

资源 URL 统一带 ``?v=<集成版本>``：HACS 升级集成后版本号变化，浏览器不会继续
使用旧的卡片缓存。

注意：注册动作放在 ``async_setup``（组件级）而不是 ``async_setup_entry``——
静态路径重复注册会抛 ``RuntimeError``，而配置条目可以有多个。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import CARD_URL, FRONTEND_URL_BASE, INTEGRATION_VERSION

try:  # HA 曾短暂存在 async_register_extra_js_url，现已移除，仅保留 add_extra_js_url
    from homeassistant.components.frontend import add_extra_js_url
except ImportError:  # pragma: no cover - 极旧或极新的 HA 版本兜底
    add_extra_js_url = None  # type: ignore[assignment]

try:
    from homeassistant.components.lovelace.resources import ResourceStorageCollection
except ImportError:  # pragma: no cover
    ResourceStorageCollection = None  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

# hass.data 中 Lovelace 数据的键名（homeassistant.components.lovelace.const.LOVELACE_DATA）
LOVELACE_DATA_KEY = "lovelace"

# 集成自带的 www/ 目录，将整体挂载到 FRONTEND_URL_BASE 前缀下
WWW_DIR = Path(__file__).parent / "www"

# Lovelace 资源集合可能晚于本集成就绪：每 5 秒重试一次，最多 12 次（约 60 秒）
_RETRY_DELAY = 5
_MAX_RETRY = 12


async def async_register_frontend(hass: HomeAssistant) -> None:
    """注册静态路径并自动登记卡片资源。可重复调用（幂等）。"""
    await _async_register_static_path(hass)
    await _async_register_card_resource(hass, _MAX_RETRY)


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """把集成内的 www/ 暴露为可访问的静态目录。

    ``cache_headers=True`` 让浏览器长缓存；缓存穿透由 URL 上的 ``?v=`` 参数负责。
    """
    if not WWW_DIR.is_dir():
        _LOGGER.warning("前端目录不存在，跳过卡片静态资源注册: %s", WWW_DIR)
        return

    from homeassistant.components.http import StaticPathConfig

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, str(WWW_DIR), True)]
        )
    except RuntimeError:
        # 已注册（例如集成重载）——正常情况，无需处理
        _LOGGER.debug("静态路径已存在，跳过: %s", FRONTEND_URL_BASE)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册卡片静态路径失败: %s", err)
    else:
        _LOGGER.debug("已注册卡片静态路径: %s -> %s", FRONTEND_URL_BASE, WWW_DIR)


async def _async_register_card_resource(
    hass: HomeAssistant, retries_left: int,
) -> None:
    """把卡片 JS 登记为 Lovelace 资源；storage 模式不可用时退回全局注入。"""
    url = f"{CARD_URL}?v={INTEGRATION_VERSION}"

    resources = _get_resources(hass.data.get(LOVELACE_DATA_KEY))
    if resources is None:
        _retry_later(hass, retries_left, "Lovelace 组件尚未就绪")
        return

    # storage 集合是惰性加载的：不先加载就调 async_items() 会拿到空列表，
    # 于是在每次重启时都误判为「资源不存在」而重复创建条目。
    # async_get_info() 内部会 _async_ensure_loaded()，YAML 集合则天然是 loaded。
    if hasattr(resources, "async_get_info"):
        try:
            await resources.async_get_info()
        except Exception as err:  # noqa: BLE001
            _retry_later(hass, retries_left, f"加载 Lovelace 资源集合失败: {err}")
            return

    existing = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).startswith(CARD_URL)
    ]

    if ResourceStorageCollection is not None and isinstance(
        resources, ResourceStorageCollection,
    ):
        # storage 模式：写入 / 更新资源表（用户可在「设置 → 仪表盘 → 资源」看到）
        for item in existing:
            if item.get("url") == url:
                _LOGGER.debug("卡片资源已是最新，无需变更: %s", url)
                return
            _LOGGER.info("卡片资源地址更新: %s -> %s", item.get("url"), url)
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": url},
            )
            return

        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("已自动登记 Lovelace 卡片资源: %s", url)
        return

    # YAML 资源模式（或非 storage 集合）：无法写入，退回全局 extra module 注入
    if existing:
        _LOGGER.debug(
            "YAML 资源模式下已存在卡片资源，保持不动: %s", existing[0].get("url"),
        )
        return

    if add_extra_js_url is None:
        _LOGGER.warning(
            "当前 HA 版本不支持自动全局注入，请手动添加卡片资源: %s", url,
        )
        return

    try:
        add_extra_js_url(hass, url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("全局注入卡片模块失败，请手动添加资源 %s: %s", url, err)
        return
    _LOGGER.info("Lovelace 资源为 YAML 模式，已全局注入卡片模块: %s", url)


def _get_resources(lovelace: Any) -> Any | None:
    """取出 Lovelace 资源集合。

    兼容 ``hass.data["lovelace"]`` 的两种历史形态：新版是 ``LovelaceData``
    dataclass（``.resources``），旧版是 dict（``["resources"]``）。
    """
    if lovelace is None:
        return None
    resources = getattr(lovelace, "resources", None)
    if resources is None and isinstance(lovelace, dict):
        resources = lovelace.get("resources")
    return resources


def _retry_later(hass: HomeAssistant, retries_left: int, reason: str) -> None:
    """资源集合未就绪时延迟重试，用尽次数后放弃（不影响集成主体功能）。"""
    if retries_left <= 0:
        _LOGGER.warning(
            "%s，放弃自动登记卡片资源（集成功能不受影响；可重启 HA 重试）", reason,
        )
        return
    _LOGGER.debug("%s，%d 秒后重试（剩余 %d 次）", reason, _RETRY_DELAY, retries_left)
    async_call_later(
        hass,
        _RETRY_DELAY,
        lambda _now: hass.async_create_task(
            _async_register_card_resource(hass, retries_left - 1)
        ),
    )
