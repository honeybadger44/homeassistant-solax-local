"""Data update coordinator for SolaX Local Control."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolaxAuthError, SolaxError, SolaxLocalApi, SolaxSnapshot
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SolaxDataUpdateCoordinator(DataUpdateCoordinator[SolaxSnapshot]):
    """Poll all SolaX values together."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: SolaxLocalApi
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
            config_entry=entry,
        )
        self.api = api

    async def _async_update_data(self) -> SolaxSnapshot:
        """Fetch a fresh validated snapshot."""
        try:
            return await self.api.async_get_snapshot()
        except SolaxAuthError as err:
            raise ConfigEntryAuthFailed from err
        except SolaxError as err:
            raise UpdateFailed(str(err)) from err
