"""Config flow for SolaX Local Control."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SolaxAuthError,
    SolaxConnectionError,
    SolaxLocalApi,
    SolaxProtocolError,
    SolaxUnsupportedDeviceError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SolaxLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolaX Local Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate and create a local dongle entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = SolaxLocalApi(
                user_input[CONF_HOST],
                user_input[CONF_PASSWORD],
                async_get_clientsession(self.hass),
            )
            try:
                await api.async_login()
                snapshot = await api.async_get_snapshot()
            except SolaxAuthError:
                errors["base"] = "invalid_auth"
            except SolaxUnsupportedDeviceError:
                errors["base"] = "unsupported_device"
            except (SolaxConnectionError, SolaxProtocolError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during SolaX setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(snapshot.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SolaX {snapshot.serial_number}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

