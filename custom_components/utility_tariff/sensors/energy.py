"""Energy tracking sensors for Utility Tariff integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import Event, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase

_LOGGER = logging.getLogger(__name__)


class UtilityEnergyDeliveredTotalSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for total energy delivered to customer (consumption)."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "energy_delivered", "Energy Delivered")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 3
        self._attr_icon = "mdi:transmission-tower-import"
        
        # Track cumulative energy received
        self._cumulative_received = 0.0
        self._last_value = None
        self._tracking_unsub = None
        
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._cumulative_received = float(last_state.state)
                    _LOGGER.info(
                        "Restored energy delivered total: %s kWh",
                        self._cumulative_received
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore energy delivered total state: %s",
                        last_state.state
                    )
                    self._cumulative_received = 0.0
            
            # Try to restore last tracked value from attributes
            if last_state.attributes:
                try:
                    self._last_value = last_state.attributes.get("last_value")
                except (ValueError, TypeError):
                    pass
        
        # Get initial value
        self._update_initial_value()
        
        # Set up state tracking for source entity
        consumption_entity = self._config_entry.options.get("consumption_entity", "none")
        
        if consumption_entity != "none":
            self._tracking_unsub = async_track_state_change_event(
                self.hass,
                [consumption_entity],
                self._handle_source_state_change,
            )
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        await super().async_will_remove_from_hass()
        if self._tracking_unsub:
            self._tracking_unsub()
    
    def _update_initial_value(self) -> None:
        """Get initial value from source entity."""
        consumption_entity = self._config_entry.options.get("consumption_entity", "none")
        
        if consumption_entity != "none":
            consumption_state = self.hass.states.get(consumption_entity)
            if consumption_state and consumption_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    value = float(consumption_state.state)
                    # Convert Wh to kWh if needed
                    if consumption_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                        value = value / 1000.0
                    if self._last_value is None:
                        self._last_value = value
                        _LOGGER.info("Set initial energy delivered value: %s kWh", value)
                except (ValueError, TypeError):
                    pass
    
    @callback
    def _handle_source_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        try:
            new_value = float(new_state.state)
            
            # Convert Wh to kWh if needed
            if new_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000.0
            
            # Calculate delta
            if self._last_value is not None:
                if new_value >= self._last_value:
                    # Normal increase
                    delta = new_value - self._last_value
                    self._cumulative_received += delta
                    _LOGGER.debug(
                        "Energy delivered increased by %s kWh, total: %s kWh",
                        delta,
                        self._cumulative_received
                    )
                else:
                    # Meter reset - use new value as delta
                    self._cumulative_received += new_value
                    _LOGGER.info(
                        "Consumption meter reset detected, adding %s kWh, total: %s kWh",
                        new_value,
                        self._cumulative_received
                    )
            else:
                # First reading - just set baseline
                _LOGGER.info("Setting initial energy delivered baseline to %s kWh", new_value)
            
            self._last_value = new_value
            self.async_write_ha_state()
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update energy delivered total: %s", err)
    
    @property
    def native_value(self) -> StateType:
        """Return cumulative energy delivered for utility meter tracking."""
        return round(self._cumulative_received, 3)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        consumption_entity = self._config_entry.options.get("consumption_entity", "none")
        
        attrs = {
            "meter_type": "energy_delivered_total",
            "source_entity": consumption_entity if consumption_entity != "none" else None,
            "last_value": self._last_value,
            "cumulative_delivered": self._cumulative_received,
        }
        
        # Add current reading if entity is configured
        if consumption_entity != "none":
            consumption_state = self.hass.states.get(consumption_entity)
            if consumption_state and consumption_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    current_value = float(consumption_state.state)
                    # Convert Wh to kWh if needed
                    if consumption_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                        current_value = current_value / 1000.0
                    attrs["current_reading"] = current_value
                except (ValueError, TypeError):
                    pass
        
        return attrs


class UtilityEnergyReceivedTotalSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for total energy received from customer (export to grid)."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "energy_received", "Energy Received")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 3
        self._attr_icon = "mdi:transmission-tower-export"
        
        # Track cumulative energy received
        self._cumulative_received = 0.0
        self._last_value = None
        self._tracking_unsub = None
        
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._cumulative_received = float(last_state.state)
                    _LOGGER.info(
                        "Restored energy received total: %s kWh",
                        self._cumulative_received
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore energy received total state: %s",
                        last_state.state
                    )
                    self._cumulative_received = 0.0
            
            # Try to restore last tracked value from attributes
            if last_state.attributes:
                try:
                    self._last_value = last_state.attributes.get("last_value")
                except (ValueError, TypeError):
                    pass
        
        # Get initial value
        self._update_initial_value()
        
        # Set up state tracking for source entity
        return_entity = self._config_entry.options.get("return_entity", "none")
        
        if return_entity != "none":
            self._tracking_unsub = async_track_state_change_event(
                self.hass,
                [return_entity],
                self._handle_source_state_change,
            )
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        await super().async_will_remove_from_hass()
        if self._tracking_unsub:
            self._tracking_unsub()
    
    def _update_initial_value(self) -> None:
        """Get initial value from source entity."""
        return_entity = self._config_entry.options.get("return_entity", "none")
        
        if return_entity != "none":
            return_state = self.hass.states.get(return_entity)
            if return_state and return_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    value = float(return_state.state)
                    # Convert Wh to kWh if needed
                    if return_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                        value = value / 1000.0
                    if self._last_value is None:
                        self._last_value = value
                        _LOGGER.info("Set initial energy received value: %s kWh", value)
                except (ValueError, TypeError):
                    pass
    
    @callback
    def _handle_source_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        try:
            new_value = float(new_state.state)
            
            # Convert Wh to kWh if needed
            if new_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000.0
            
            # Calculate delta
            if self._last_value is not None:
                if new_value >= self._last_value:
                    # Normal increase
                    delta = new_value - self._last_value
                    self._cumulative_received += delta
                    _LOGGER.debug(
                        "Energy received increased by %s kWh, total: %s kWh",
                        delta,
                        self._cumulative_received
                    )
                else:
                    # Meter reset - use new value as delta
                    self._cumulative_received += new_value
                    _LOGGER.info(
                        "Return meter reset detected, adding %s kWh, total: %s kWh",
                        new_value,
                        self._cumulative_received
                    )
            else:
                # First reading - just set baseline
                _LOGGER.info("Setting initial energy received baseline to %s kWh", new_value)
            
            self._last_value = new_value
            self.async_write_ha_state()
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update energy received total: %s", err)
    
    @property
    def native_value(self) -> StateType:
        """Return cumulative energy received for utility meter tracking."""
        return round(self._cumulative_received, 3)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return_entity = self._config_entry.options.get("return_entity", "none")
        
        attrs = {
            "meter_type": "energy_received_total",
            "source_entity": return_entity if return_entity != "none" else None,
            "last_value": self._last_value,
            "cumulative_received": self._cumulative_received,
        }
        
        # Add current reading if entity is configured
        if return_entity != "none":
            return_state = self.hass.states.get(return_entity)
            if return_state and return_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    current_value = float(return_state.state)
                    # Convert Wh to kWh if needed
                    if return_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                        current_value = current_value / 1000.0
                    attrs["current_reading"] = current_value
                except (ValueError, TypeError):
                    pass
        
        return attrs