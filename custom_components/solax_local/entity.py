"""Shared entities for SolaX Local Control."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolaxDataUpdateCoordinator


class SolaxEntity(CoordinatorEntity[SolaxDataUpdateCoordinator]):
    """Base entity attached to one SolaX inverter."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolaxDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        snapshot = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, snapshot.serial_number)},
            name="SolaX X1-BOOST-5K-G4",
            manufacturer="SolaX Power",
            model="X1-BOOST-5K-G4",
            serial_number=snapshot.serial_number,
            sw_version=snapshot.firmware_version,
        )

