"""Total cost sensor for TOU that sums period costs."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    RestoreEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from custom_components.utility_tariff.const import DOMAIN, ALL_STATES

_LOGGER = logging.getLogger(__name__)


class UtilityTOUTotalCostSensor(SensorEntity, RestoreEntity):
    """Sensor that sums TOU period costs."""
    
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash-multiple"
    _attr_suggested_display_precision = 2
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the total cost sensor."""
        self._hass = hass
        self._config_entry = config_entry
        self._peak_cost_entity = None
        self._shoulder_cost_entity = None
        self._off_peak_cost_entity = None
        
        # State tracking
        self._peak_cost = 0.0
        self._shoulder_cost = 0.0
        self._off_peak_cost = 0.0
        self._tracking_unsubs = []
        
        # Get provider info for device
        try:
            provider_data = hass.data[DOMAIN][config_entry.entry_id]
            provider = provider_data["provider"]
            state = config_entry.data["state"]
            state_name = provider_data.get("state_name", ALL_STATES.get(state, state))
            provider_name = provider.name
        except (KeyError, AttributeError):
            # Fallback if data not yet available
            provider_name = config_entry.data.get("provider", "Unknown")
            state = config_entry.data.get("state", "Unknown")
            state_name = ALL_STATES.get(state, state)
        
        # Set up entity attributes
        self._attr_name = "Total Energy Cost"
        self._attr_unique_id = f"{config_entry.entry_id}_total_energy_cost"
        self._attr_has_entity_name = True
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider_name} {state_name}",
            "manufacturer": provider_name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    @property
    def native_value(self) -> StateType:
        """Return the sum of all period costs."""
        return self._peak_cost + self._shoulder_cost + self._off_peak_cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "peak_cost": self._peak_cost,
            "shoulder_cost": self._shoulder_cost,
            "off_peak_cost": self._off_peak_cost,
            "peak_cost_entity": self._peak_cost_entity,
            "shoulder_cost_entity": self._shoulder_cost_entity,
            "off_peak_cost_entity": self._off_peak_cost_entity,
        }
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Find cost meter entities from integration data
        tou_cost_meters = self.hass.data.get(DOMAIN, {}).get(
            self._config_entry.entry_id, {}
        ).get("tou_cost_meters", {})
        
        if tou_cost_meters:
            self._peak_cost_entity = tou_cost_meters["peak"].entity_id
            self._shoulder_cost_entity = tou_cost_meters["shoulder"].entity_id
            self._off_peak_cost_entity = tou_cost_meters["off_peak"].entity_id
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.attributes:
                self._peak_cost = last_state.attributes.get("peak_cost", 0.0)
                self._shoulder_cost = last_state.attributes.get("shoulder_cost", 0.0)
                self._off_peak_cost = last_state.attributes.get("off_peak_cost", 0.0)
        
        # Track all three cost entities if we found them
        if self._peak_cost_entity and self._shoulder_cost_entity and self._off_peak_cost_entity:
            self._tracking_unsubs.append(
                async_track_state_change_event(
                    self.hass,
                    [self._peak_cost_entity, self._shoulder_cost_entity, self._off_peak_cost_entity],
                    self._handle_cost_change
                )
            )
        
        # Get initial values
        await self._update_costs()
    
    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        for unsub in self._tracking_unsubs:
            unsub()
        self._tracking_unsubs.clear()
    
    async def _update_costs(self) -> None:
        """Update costs from source entities."""
        # Peak cost
        if self._peak_cost_entity:
            peak_state = self.hass.states.get(self._peak_cost_entity)
            if peak_state and peak_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._peak_cost = float(peak_state.state)
                except (ValueError, TypeError):
                    pass
        
        # Shoulder cost
        if self._shoulder_cost_entity:
            shoulder_state = self.hass.states.get(self._shoulder_cost_entity)
            if shoulder_state and shoulder_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._shoulder_cost = float(shoulder_state.state)
                except (ValueError, TypeError):
                    pass
        
        # Off-peak cost
        if self._off_peak_cost_entity:
            off_peak_state = self.hass.states.get(self._off_peak_cost_entity)
            if off_peak_state and off_peak_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._off_peak_cost = float(off_peak_state.state)
                except (ValueError, TypeError):
                    pass
    
    @callback
    async def _handle_cost_change(self, event) -> None:
        """Handle changes in period costs."""
        await self._update_costs()
        self.async_write_ha_state()