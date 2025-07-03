"""Internal utility meter sensors for Utility Tariff integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    RestoreEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ALL_STATES

_LOGGER = logging.getLogger(__name__)


class UtilityTariffMeter(SensorEntity, RestoreEntity):
    """Internal utility meter that tracks energy consumption with automatic resets."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:meter-electric-outline"
    _attr_suggested_display_precision = 3
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        source_entity: str,
        cycle: str,
        cycle_name: str,
        meter_type: str = "net_consumption",
    ) -> None:
        """Initialize the utility meter."""
        self._hass = hass
        self._config_entry = config_entry
        self._source_entity = source_entity
        self._cycle = cycle
        self._cycle_name = cycle_name
        self._meter_type = meter_type
        
        # State tracking
        self._total_consumed = 0.0
        self._last_value = None
        self._last_reset = dt_util.now()
        self._tracking_unsub = None
        self._reset_unsub = None
        self._attr_available = True
        
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
        self._attr_name = cycle_name
        self._attr_unique_id = f"{config_entry.entry_id}_{meter_type}_meter_{cycle}"
        self._attr_has_entity_name = True
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider_name} {state_name}",
            "manufacturer": provider_name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    @property
    def native_value(self) -> StateType:
        """Return the current meter value."""
        return self._total_consumed
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "meter_type": self._meter_type,
            "source_entity": self._source_entity,
            "cycle": self._cycle,
            "last_value": self._last_value,
            "last_reset": self._last_reset.isoformat() if self._last_reset else None,
        }
        
        # Add cycle-specific information
        if self._cycle == "daily":
            attrs["reset_time"] = "00:00:00"
            attrs["next_reset"] = self._get_next_reset_time()
        elif self._cycle == "weekly":
            attrs["reset_day"] = "Monday"
            attrs["next_reset"] = self._get_next_reset_time()
        elif self._cycle == "monthly":
            attrs["reset_day"] = "1st of month"
            attrs["next_reset"] = self._get_next_reset_time()
        elif self._cycle == "quarterly":
            attrs["reset_months"] = "January, April, July, October"
            attrs["next_reset"] = self._get_next_reset_time()
        
        return attrs
    
    def _get_next_reset_time(self) -> str | None:
        """Get the next reset time as a string."""
        if not self._last_reset:
            return None
        
        now = dt_util.now()
        
        if self._cycle == "daily":
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self._cycle == "weekly":
            days_ahead = 7 - now.weekday()  # Monday is 0
            if days_ahead == 7:  # If it's Monday
                days_ahead = 7
            next_reset = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self._cycle == "monthly":
            if now.month == 12:
                next_reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self._cycle == "quarterly":
            current_quarter = (now.month - 1) // 3 + 1
            if current_quarter == 4:
                next_reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_month = current_quarter * 3 + 1
                next_reset = now.replace(month=next_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return None
        
        return next_reset.isoformat()
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._total_consumed = float(last_state.state)
                    _LOGGER.info(
                        "Restored utility meter %s: %s kWh",
                        self._cycle_name,
                        self._total_consumed
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore state for %s: %s",
                        self._cycle_name,
                        last_state.state
                    )
                    self._total_consumed = 0.0
            else:
                self._total_consumed = 0.0
            
            # Try to restore last tracked value from attributes
            if last_state.attributes and "last_value" in last_state.attributes:
                try:
                    self._last_value = float(last_state.attributes["last_value"])
                    _LOGGER.debug(
                        "Restored last tracked value for %s: %s",
                        self._cycle_name,
                        self._last_value
                    )
                except (ValueError, TypeError):
                    pass
            
            # Try to restore last reset time
            if last_state.attributes and "last_reset" in last_state.attributes:
                try:
                    self._last_reset = datetime.fromisoformat(last_state.attributes["last_reset"])
                except (ValueError, TypeError):
                    self._last_reset = dt_util.now()
        else:
            self._total_consumed = 0.0
            self._last_reset = dt_util.now()
        
        # Only get initial value from source entity if we didn't restore last_value
        if self._last_value is None:
            source_state = self.hass.states.get(self._source_entity)
            if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    new_value = float(source_state.state)
                    
                    # Handle unit conversion from Wh to kWh if needed
                    source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                    if source_unit == UnitOfEnergy.WATT_HOUR:
                        new_value = new_value / 1000  # Convert Wh to kWh
                        _LOGGER.debug(
                            "Utility meter %s: Converting initial value %s Wh to %s kWh",
                            self._cycle_name,
                            source_state.state,
                            new_value
                        )
                    
                    self._last_value = new_value
                    _LOGGER.info(
                        "Utility meter %s set initial baseline from source entity %s: %s kWh",
                        self._cycle_name,
                        self._source_entity,
                        self._last_value
                    )
                except (ValueError, TypeError):
                    self._last_value = None
                    _LOGGER.warning(
                        "Utility meter %s found source entity %s but could not parse value: %s",
                        self._cycle_name,
                        self._source_entity,
                        source_state.state
                    )
            else:
                _LOGGER.warning(
                    "Utility meter %s could not find source entity for initial baseline: %s",
                    self._cycle_name,
                    self._source_entity
                )
        else:
            _LOGGER.info(
                "Utility meter %s using restored last_value: %s kWh",
                self._cycle_name,
                self._last_value
            )
            # Verify the restored value is still valid compared to current source
            source_state = self.hass.states.get(self._source_entity)
            if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    current_value = float(source_state.state)
                    # Handle unit conversion
                    source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                    if source_unit == UnitOfEnergy.WATT_HOUR:
                        current_value = current_value / 1000
                    
                    # If current value is significantly lower than last tracked value,
                    # the source meter probably reset while we were offline
                    if current_value < self._last_value * 0.5:  # 50% threshold
                        _LOGGER.warning(
                            "Utility meter %s detected possible source reset while offline: "
                            "last tracked %s kWh, current %s kWh. Using current as new baseline.",
                            self._cycle_name,
                            self._last_value,
                            current_value
                        )
                        self._last_value = current_value
                except (ValueError, TypeError):
                    pass
        
        # Set up state tracking
        self._tracking_unsub = async_track_state_change_event(
            self.hass,
            [self._source_entity],
            self._handle_state_change,
        )
        
        # Set up periodic reset checking
        self._reset_unsub = async_track_time_interval(
            self.hass,
            self._check_reset_needed,
            timedelta(minutes=1)  # Check every minute
        )
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        if self._tracking_unsub:
            self._tracking_unsub()
        if self._reset_unsub:
            self._reset_unsub()
    
    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self.async_write_ha_state()
            return
        
        try:
            new_value = float(new_state.state)
            
            # Handle unit conversion from Wh to kWh if needed
            source_unit = new_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
            if source_unit == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000  # Convert Wh to kWh
                _LOGGER.debug(
                    "Utility meter %s: Converting %s Wh to %s kWh",
                    self._cycle_name,
                    new_state.state,
                    new_value
                )
            
            # Calculate consumption since last reading
            if self._last_value is not None:
                if new_value >= self._last_value:
                    # Normal increase
                    consumption = new_value - self._last_value
                    self._total_consumed += consumption
                    _LOGGER.debug(
                        "Utility meter %s: %s -> %s (+%s kWh), total: %s kWh",
                        self._cycle_name,
                        self._last_value,
                        new_value,
                        consumption,
                        self._total_consumed
                    )
                else:
                    # Source meter reset or rollover - just update baseline, don't add to consumption
                    _LOGGER.info(
                        "Source meter reset detected for %s: %s -> %s, updating baseline only",
                        self._cycle_name,
                        self._last_value,
                        new_value
                    )
            else:
                # First reading - just set the baseline
                _LOGGER.info(
                    "Utility meter %s: Setting initial baseline to %s kWh",
                    self._cycle_name,
                    new_value
                )
            
            self._last_value = new_value
            self._attr_available = True
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update utility meter %s: %s", self._cycle_name, err)
            self._attr_available = False
        
        self.async_write_ha_state()
    
    @callback
    def _check_reset_needed(self, now: datetime) -> None:
        """Check if meter needs to be reset based on cycle."""
        if not self._last_reset:
            return
        
        should_reset = False
        
        if self._cycle == "daily":
            # Reset at midnight
            should_reset = now.date() > self._last_reset.date()
        elif self._cycle == "weekly":
            # Reset on Monday
            days_since_reset = (now.date() - self._last_reset.date()).days
            should_reset = (
                days_since_reset >= 7 or
                (days_since_reset > 0 and now.weekday() == 0 and self._last_reset.weekday() != 0)
            )
        elif self._cycle == "monthly":
            # Reset on 1st of month
            should_reset = (
                now.month != self._last_reset.month or
                now.year != self._last_reset.year
            )
        elif self._cycle == "quarterly":
            # Reset on 1st of quarter months (Jan, Apr, Jul, Oct)
            current_quarter = (now.month - 1) // 3 + 1
            reset_quarter = (self._last_reset.month - 1) // 3 + 1
            should_reset = (
                current_quarter != reset_quarter or
                now.year != self._last_reset.year
            )
        
        if should_reset:
            self._reset_meter()
    
    @callback
    def _reset_meter(self) -> None:
        """Reset the meter value."""
        old_value = self._total_consumed
        self._total_consumed = 0.0
        self._last_reset = dt_util.now()
        
        # Get current value of source entity to use as new baseline
        source_state = self.hass.states.get(self._source_entity)
        if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                new_value = float(source_state.state)
                
                # Handle unit conversion from Wh to kWh if needed
                source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                if source_unit == UnitOfEnergy.WATT_HOUR:
                    new_value = new_value / 1000  # Convert Wh to kWh
                
                self._last_value = new_value
            except (ValueError, TypeError):
                _LOGGER.warning("Could not get current value for reset baseline")
        
        _LOGGER.info(
            "Reset %s utility meter: %s kWh -> 0.0 kWh",
            self._cycle_name,
            old_value
        )
        
        self.async_write_ha_state()
    
    async def async_reset(self) -> None:
        """Manual reset service call."""
        _LOGGER.info("Manual reset requested for %s utility meter", self._cycle_name)
        self._reset_meter()


class UtilityTariffTOUMeter(SensorEntity, RestoreEntity):
    """TOU-based utility meter that tracks energy by time-of-use period."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:meter-electric-outline"
    _attr_suggested_display_precision = 3
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        source_entity: str,
        tou_period: str,
        period_name: str,
        meter_type: str = "energy_received",
    ) -> None:
        """Initialize the TOU utility meter."""
        self._hass = hass
        self._config_entry = config_entry
        self._source_entity = source_entity
        self._tou_period = tou_period
        self._period_name = period_name
        self._meter_type = meter_type
        
        # State tracking
        self._total_consumed = 0.0
        self._last_value = None
        self._last_reset = dt_util.now()
        self._tracking_unsub = None
        self._period_check_unsub = None
        self._current_tou_period = None
        self._attr_available = True
        
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
        self._attr_name = period_name
        self._attr_unique_id = f"{config_entry.entry_id}_{meter_type}_{tou_period}_meter"
        self._attr_has_entity_name = True
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider_name} {state_name}",
            "manufacturer": provider_name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    @property
    def native_value(self) -> StateType:
        """Return the current meter value."""
        return self._total_consumed
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "meter_type": self._meter_type,
            "tou_period": self._tou_period,
            "source_entity": self._source_entity,
            "last_value": self._last_value,
            "last_reset": self._last_reset.isoformat() if self._last_reset else None,
            "currently_tracking": self._current_tou_period == self._tou_period,
        }
        
        return attrs
    
    @callback
    def _check_tou_period(self, now: datetime) -> None:
        """Periodic check for TOU period changes."""
        old_period = self._current_tou_period
        self._update_current_tou_period()
        
        # Force state update if period changed or if we're now tracking
        if old_period != self._current_tou_period:
            _LOGGER.info(
                "TOU meter %s period changed from %s to %s during periodic check",
                self._period_name,
                old_period,
                self._current_tou_period
            )
            self.async_write_ha_state()
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._total_consumed = float(last_state.state)
                    _LOGGER.info(
                        "Restored TOU utility meter %s: %s kWh",
                        self._period_name,
                        self._total_consumed
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore state for %s: %s",
                        self._period_name,
                        last_state.state
                    )
                    self._total_consumed = 0.0
            else:
                self._total_consumed = 0.0
            
            # Try to restore last tracked value from attributes
            if last_state.attributes and "last_value" in last_state.attributes:
                try:
                    self._last_value = float(last_state.attributes["last_value"])
                    _LOGGER.debug(
                        "Restored last tracked value for %s: %s",
                        self._period_name,
                        self._last_value
                    )
                except (ValueError, TypeError):
                    pass
            
            # Try to restore last reset time
            if last_state.attributes and "last_reset" in last_state.attributes:
                try:
                    self._last_reset = datetime.fromisoformat(last_state.attributes["last_reset"])
                except (ValueError, TypeError):
                    self._last_reset = dt_util.now()
        else:
            self._total_consumed = 0.0
            self._last_reset = dt_util.now()
        
        # Only get initial value from source entity if we didn't restore last_value
        if self._last_value is None:
            source_state = self.hass.states.get(self._source_entity)
            if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    new_value = float(source_state.state)
                    
                    # Handle unit conversion from Wh to kWh if needed
                    source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                    if source_unit == UnitOfEnergy.WATT_HOUR:
                        new_value = new_value / 1000  # Convert Wh to kWh
                        _LOGGER.debug(
                            "TOU utility meter %s: Converting initial value %s Wh to %s kWh",
                            self._period_name,
                            source_state.state,
                            new_value
                        )
                    
                    self._last_value = new_value
                    _LOGGER.info(
                        "TOU utility meter %s set initial baseline from source entity %s: %s kWh",
                        self._period_name,
                        self._source_entity,
                        self._last_value
                    )
                except (ValueError, TypeError):
                    self._last_value = None
                    _LOGGER.warning(
                        "TOU utility meter %s found source entity %s but could not parse value: %s",
                        self._period_name,
                        self._source_entity,
                        source_state.state
                    )
            else:
                _LOGGER.warning(
                    "TOU utility meter %s could not find source entity for initial baseline: %s",
                    self._period_name,
                    self._source_entity
                )
        else:
            _LOGGER.info(
                "TOU utility meter %s using restored last_value: %s kWh",
                self._period_name,
                self._last_value
            )
            # Verify the restored value is still valid compared to current source
            source_state = self.hass.states.get(self._source_entity)
            if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    current_value = float(source_state.state)
                    # Handle unit conversion
                    source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                    if source_unit == UnitOfEnergy.WATT_HOUR:
                        current_value = current_value / 1000
                    
                    # If current value is significantly lower than last tracked value,
                    # the source meter probably reset while we were offline
                    if current_value < self._last_value * 0.5:  # 50% threshold
                        _LOGGER.warning(
                            "TOU utility meter %s detected possible source reset while offline: "
                            "last tracked %s kWh, current %s kWh. Using current as new baseline.",
                            self._period_name,
                            self._last_value,
                            current_value
                        )
                        self._last_value = current_value
                except (ValueError, TypeError):
                    pass
        
        # Set up state tracking
        self._tracking_unsub = async_track_state_change_event(
            self.hass,
            [self._source_entity],
            self._handle_state_change,
        )
        
        # Also track TOU period changes
        self._update_current_tou_period()
        _LOGGER.info(
            "TOU meter %s initialized for period %s, current period is %s, source: %s",
            self._period_name,
            self._tou_period,
            self._current_tou_period,
            self._source_entity
        )
        
        # Set up periodic TOU period check (every minute)
        self._period_check_unsub = async_track_time_interval(
            self.hass,
            self._check_tou_period,
            timedelta(minutes=1)
        )
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        if self._tracking_unsub:
            self._tracking_unsub()
        if self._period_check_unsub:
            self._period_check_unsub()
    
    def _update_current_tou_period(self) -> None:
        """Update the current TOU period from the coordinator."""
        # Get the TOU period sensor
        provider_data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
        dynamic_coordinator = provider_data.get("dynamic_coordinator")
        
        _LOGGER.debug(
            "TOU meter %s checking period - provider_data keys: %s",
            self._period_name,
            list(provider_data.keys()) if provider_data else "None"
        )
        
        if dynamic_coordinator:
            _LOGGER.debug(
                "TOU meter %s - coordinator exists, has data: %s, data keys: %s",
                self._period_name,
                bool(dynamic_coordinator.data),
                list(dynamic_coordinator.data.keys()) if dynamic_coordinator.data else "None"
            )
            
            if dynamic_coordinator.data:
                # Get current period directly from coordinator data
                new_period = dynamic_coordinator.data.get("current_period", "")
                if new_period:
                    # Normalize the period name
                    new_period = new_period.lower().replace("-", "_")
                    _LOGGER.debug(
                        "TOU meter %s found current_period: %s (raw: %s)",
                        self._period_name,
                        new_period,
                        dynamic_coordinator.data.get("current_period")
                    )
                else:
                    _LOGGER.warning(
                        "TOU meter %s - no current_period in coordinator data. Available keys: %s",
                        self._period_name,
                        list(dynamic_coordinator.data.keys())
                    )
                
                if new_period and new_period != self._current_tou_period:
                    _LOGGER.info(
                        "TOU period changed from %s to %s for meter %s",
                        self._current_tou_period,
                        new_period,
                        self._period_name
                    )
                    self._current_tou_period = new_period
                elif not new_period:
                    _LOGGER.warning(
                        "TOU meter %s got empty period from coordinator (tou_info: %s, current_period: %s)",
                        self._period_name,
                        tou_info,
                        dynamic_coordinator.data.get("current_period")
                    )
            else:
                _LOGGER.warning("TOU meter %s - coordinator has no data", self._period_name)
        else:
            _LOGGER.warning("TOU meter %s - no coordinator found in provider_data", self._period_name)
    
    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self.async_write_ha_state()
            return
        
        _LOGGER.debug(
            "TOU meter %s handling state change from %s: %s -> %s",
            self._period_name,
            self._source_entity,
            event.data.get("old_state").state if event.data.get("old_state") else "None",
            new_state.state
        )
        
        # Update current TOU period synchronously
        self._update_current_tou_period()
        
        # Only track consumption if we're in the correct TOU period
        if self._current_tou_period != self._tou_period:
            # Not our period, just update the baseline value
            try:
                new_value = float(new_state.state)
                
                # Handle unit conversion from Wh to kWh if needed
                source_unit = new_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                if source_unit == UnitOfEnergy.WATT_HOUR:
                    new_value = new_value / 1000  # Convert Wh to kWh
                
                if self._last_value != new_value:
                    _LOGGER.debug(
                        "TOU meter %s: Not tracking (current period: %s, my period: %s), updating baseline to %s kWh",
                        self._period_name,
                        self._current_tou_period,
                        self._tou_period,
                        new_value
                    )
                    self._last_value = new_value
            except (ValueError, TypeError):
                pass
            self.async_write_ha_state()  # Update state to show current tracking status
            return
        
        try:
            new_value = float(new_state.state)
            
            # Handle unit conversion from Wh to kWh if needed
            source_unit = new_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
            if source_unit == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000  # Convert Wh to kWh
                _LOGGER.debug(
                    "TOU utility meter %s: Converting %s Wh to %s kWh",
                    self._period_name,
                    new_state.state,
                    new_value
                )
            
            # Calculate consumption since last reading
            if self._last_value is not None:
                if new_value >= self._last_value:
                    # Normal increase
                    consumption = new_value - self._last_value
                    self._total_consumed += consumption
                    _LOGGER.debug(
                        "TOU utility meter %s (%s period): %s -> %s (+%s kWh), total: %s kWh",
                        self._period_name,
                        self._tou_period,
                        self._last_value,
                        new_value,
                        consumption,
                        self._total_consumed
                    )
                else:
                    # Source meter reset or rollover - just update baseline, don't add to consumption
                    _LOGGER.info(
                        "Source meter reset detected for %s: %s -> %s, updating baseline only",
                        self._period_name,
                        self._last_value,
                        new_value
                    )
            else:
                # First reading - just set the baseline
                _LOGGER.info(
                    "TOU utility meter %s: Setting initial baseline to %s kWh",
                    self._period_name,
                    new_value
                )
            
            self._last_value = new_value
            self._attr_available = True
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update TOU utility meter %s: %s", self._period_name, err)
            self._attr_available = False
        
        self.async_write_ha_state()
    
    @callback
    def _reset_meter(self) -> None:
        """Reset the meter value."""
        old_value = self._total_consumed
        self._total_consumed = 0.0
        self._last_reset = dt_util.now()
        
        # Get current value of source entity to use as new baseline
        source_state = self.hass.states.get(self._source_entity)
        if source_state and source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                new_value = float(source_state.state)
                
                # Handle unit conversion from Wh to kWh if needed
                source_unit = source_state.attributes.get("unit_of_measurement", UnitOfEnergy.KILO_WATT_HOUR)
                if source_unit == UnitOfEnergy.WATT_HOUR:
                    new_value = new_value / 1000  # Convert Wh to kWh
                
                self._last_value = new_value
            except (ValueError, TypeError):
                _LOGGER.warning("Could not get current value for reset baseline")
        
        _LOGGER.info(
            "Reset %s TOU utility meter: %s kWh -> 0.0 kWh",
            self._period_name,
            old_value
        )
        
        self.async_write_ha_state()
    
    async def async_reset(self) -> None:
        """Manual reset service call."""
        _LOGGER.info("Manual reset requested for %s TOU utility meter", self._period_name)
        self._reset_meter()