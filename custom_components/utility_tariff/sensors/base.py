"""Base sensor class for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN, ALL_STATES


class UtilitySensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Utility sensors."""
    
    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._key = key
        
        state = config_entry.data["state"]
        # Get provider from stored data
        provider = coordinator.hass.data[DOMAIN][config_entry.entry_id]["provider"]
        
        # Use camelCase as requested, following HA naming guidelines
        self._attr_name = name  # Remove provider/state from entity name
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        self._attr_has_entity_name = True  # Enable new naming conventions
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider.name} {ALL_STATES.get(state, state)}",
            "manufacturer": provider.name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available if we have coordinator data, even if some values are None
        return self.coordinator.last_update_success and self.coordinator.data is not None