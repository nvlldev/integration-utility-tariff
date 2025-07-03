"""Button platform for Utility Tariff integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ALL_STATES, SERVICE_RESET_METER, ATTR_RESET_ALL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Utility Tariff button platform."""
    # Get provider info for device
    provider_data = hass.data[DOMAIN][config_entry.entry_id]
    provider = provider_data["provider"]
    state = config_entry.data["state"]
    state_name = provider_data.get("state_name", ALL_STATES.get(state, state))
    
    # Create reset button
    async_add_entities([
        ResetAllMetersButton(
            hass=hass,
            config_entry=config_entry,
            provider_name=provider.name,
            state_name=state_name,
        )
    ])


class ResetAllMetersButton(ButtonEntity):
    """Button to reset all utility meters."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        provider_name: str,
        state_name: str,
    ) -> None:
        """Initialize the button."""
        self._hass = hass
        self._config_entry = config_entry
        
        # Set up entity attributes
        self._attr_name = "Reset All Meters"
        self._attr_unique_id = f"{config_entry.entry_id}_reset_all_meters"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:restart"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider_name} {state_name}",
            "manufacturer": provider_name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Reset all meters button pressed")
        
        # Call the reset meter service with reset_all flag
        await self._hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_METER,
            {ATTR_RESET_ALL: True},
            blocking=True,
        )
        
        _LOGGER.info("All utility meters have been reset")