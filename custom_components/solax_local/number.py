"""Output-limit control for SolaX Local Control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SolaxError
from .const import DOMAIN, RUN_MODE_NORMAL
from .coordinator import SolaxDataUpdateCoordinator
from .entity import SolaxEntity


class SolaxOutputLimitNumber(SolaxEntity, NumberEntity):
    """Control the verified whole-inverter active-power percentage cap."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "output_limit"

    def __init__(self, coordinator: SolaxDataUpdateCoordinator) -> None:
        """Initialize the output-limit control."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.serial_number}_output_limit"

    @property
    def native_value(self) -> float:
        """Return the inverter's current readback, not an assumed value."""
        return self.coordinator.data.output_limit_percent

    @property
    def available(self) -> bool:
        """Only offer control while the inverter can accept setting writes."""
        return (
            super().available
            and self.coordinator.data.run_mode == RUN_MODE_NORMAL
        )

    async def async_set_native_value(self, value: float) -> None:
        """Write and then verify the whole-inverter output cap."""
        if self.coordinator.data.run_mode != RUN_MODE_NORMAL:
            raise HomeAssistantError(
                "The SolaX inverter is not in Normal mode; "
                "its output limit cannot be changed while it is asleep"
            )
        percent = round(value)
        try:
            await self.coordinator.api.async_set_output_limit(percent)
            await self.coordinator.async_refresh()
        except SolaxError as err:
            raise HomeAssistantError(
                f"Could not set the SolaX output limit: {err}"
            ) from err

        if not self.coordinator.last_update_success:
            raise HomeAssistantError(
                "SolaX accepted the write but its settings could not be read back"
            )
        if self.coordinator.data.output_limit_percent != percent:
            raise HomeAssistantError(
                "SolaX acknowledged the write but the readback did not match"
            )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SolaX output-limit number."""
    coordinator: SolaxDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SolaxOutputLimitNumber(coordinator)])
