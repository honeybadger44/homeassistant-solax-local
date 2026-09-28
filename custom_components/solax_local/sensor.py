"""Sensor entities for SolaX Local Control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SolaxSnapshot
from .const import DOMAIN
from .coordinator import SolaxDataUpdateCoordinator
from .entity import SolaxEntity

RUN_MODES = {
    0: "waiting",
    1: "checking",
    2: "normal",
    3: "fault",
    4: "permanent_fault",
    5: "updating",
}
EXPORT_MODES = {0: "disabled", 1: "meter", 2: "ct"}


@dataclass(frozen=True, kw_only=True)
class SolaxSensorEntityDescription(SensorEntityDescription):
    """Describe a mapped SolaX sensor."""

    value_fn: Callable[[SolaxSnapshot], Any]


SENSORS: tuple[SolaxSensorEntityDescription, ...] = (
    SolaxSensorEntityDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.ac_power_w,
    ),
    SolaxSensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.pv_power_w,
    ),
    SolaxSensorEntityDescription(
        key="pv1_power",
        translation_key="pv1_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.pv1_power_w,
    ),
    SolaxSensorEntityDescription(
        key="pv2_power",
        translation_key="pv2_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.pv2_power_w,
    ),
    SolaxSensorEntityDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ac_voltage_v,
    ),
    SolaxSensorEntityDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ac_current_a,
    ),
    SolaxSensorEntityDescription(
        key="ac_frequency",
        translation_key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ac_frequency_hz,
    ),
    SolaxSensorEntityDescription(
        key="today_yield",
        translation_key="today_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.today_yield_kwh,
    ),
    SolaxSensorEntityDescription(
        key="total_yield",
        translation_key="total_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_yield_kwh,
    ),
    SolaxSensorEntityDescription(
        key="run_mode",
        translation_key="run_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(RUN_MODES.values()) + ["unknown"],
        value_fn=lambda data: RUN_MODES.get(data.run_mode, "unknown"),
    ),
    SolaxSensorEntityDescription(
        key="export_mode",
        translation_key="export_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(EXPORT_MODES.values()) + ["unknown"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: EXPORT_MODES.get(data.export_mode, "unknown"),
    ),
    SolaxSensorEntityDescription(
        key="export_limit",
        translation_key="export_limit",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.export_limit_w,
    ),
    SolaxSensorEntityDescription(
        key="output_limit_readback",
        translation_key="output_limit_readback",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.output_limit_percent,
    ),
)


class SolaxSensor(SolaxEntity, SensorEntity):
    """A sensor backed by the shared SolaX snapshot."""

    entity_description: SolaxSensorEntityDescription

    def __init__(
        self,
        coordinator: SolaxDataUpdateCoordinator,
        description: SolaxSensorEntityDescription,
    ) -> None:
        """Initialize one mapped sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.serial_number}_{description.key}"
        )

    @property
    def native_value(self) -> Any:
        """Return the current mapped value."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SolaX sensors from a config entry."""
    coordinator: SolaxDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(SolaxSensor(coordinator, description) for description in SENSORS)

