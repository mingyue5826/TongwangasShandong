"""Config flow for 山东港华燃气 integration."""
from __future__ import annotations

import os
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

DOMAIN = "tongwangas_shandong"

_LOGGER = logging.getLogger(__name__)


def _sync_load_org_data(json_path: str) -> tuple[dict[str, str], dict[str, str]]:
    """同步读取 JSON 文件的内部函数."""
    org_options: dict[str, str] = {}
    org_host_map: dict[str, str] = {}

    if not os.path.exists(json_path):
        _LOGGER.error("未找到机构配置文件: %s", json_path)
        return org_options, org_host_map

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        org_array = []
        if isinstance(raw_data, dict):
            org_array = raw_data.get("orgList", [])
        elif isinstance(raw_data, list):
            org_array = raw_data

        for item in org_array:
            if isinstance(item, dict) and "orgId" in item and "orgName" in item:
                org_id = str(item["orgId"])
                org_name = str(item["orgName"])
                host = str(item.get("apiHost") or item.get("host") or "")

                org_options[org_id] = org_name
                org_host_map[org_id] = host

    except Exception as err:
        _LOGGER.error("读取或解析 orglist.json 失败: %s", err)

    return org_options, org_host_map


class TongwangasShandongConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 山东港华燃气."""

    VERSION = 1

    def __init__(self) -> None:
        """初始化配置流."""
        self.org_options: dict[str, str] = {}
        self.org_host_map: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """处理用户配置表单."""
        errors: dict[str, str] = {}

        if not self.org_options:
            current_dir = os.path.dirname(__file__)
            json_path = os.path.join(current_dir, "orglist.json")
            self.org_options, self.org_host_map = await self.hass.async_add_executor_job(
                _sync_load_org_data, json_path
            )

        if user_input is not None:
            org_id = user_input.get("org_id")
            access_token = user_input.get("access_token", "").strip()
            refresh_token = user_input.get("refresh_token", "").strip()
            sign = user_input.get("sign", "").strip()

            if not org_id or org_id not in self.org_options:
                errors["base"] = "invalid_org"
            elif not access_token or not refresh_token or not sign:
                errors["base"] = "missing_credentials"
            else:
                org_name = self.org_options[org_id]
                api_host = self.org_host_map.get(org_id, "")

                unique_id = f"{org_id}_{sign[-8:] if len(sign) >= 8 else sign}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{org_name}",
                    data={
                        "org_id": org_id,
                        "org_name": org_name,
                        "host": api_host,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "sign": sign,
                        "selected_subs": [],
                    },
                )

        if self.org_options:
            org_schema = vol.In(self.org_options)
        else:
            org_schema = str

        data_schema = vol.Schema(
            {
                vol.Required("org_id"): org_schema,
                vol.Required("access_token"): str,
                vol.Required("refresh_token"): str,
                vol.Required("sign"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )