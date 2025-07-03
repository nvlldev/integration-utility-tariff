"""Cost tracking utility meters for Utility Tariff integration."""
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
    CURRENCY_DOLLAR,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from custom_components.utility_tariff.const import DOMAIN, ALL_STATES

_LOGGER = logging.getLogger(__name__)


class UtilityTariffCostMeter(SensorEntity, RestoreEntity):
    """Cost meter that tracks accumulated costs based on consumption and rates."""
    
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash-multiple"
    _attr_suggested_display_precision = 2
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        source_meter_entity: str,
        coordinator,
        name: str,
        unique_id_suffix: str,
        rate_key: str = None,
        tou_period: str = None,
        meter_type: str = "energy_delivered",
    ) -> None:
        """Initialize the cost meter."""
        self._hass = hass
        self._config_entry = config_entry
        self._source_meter_entity = source_meter_entity
        self._coordinator = coordinator
        self._rate_key = rate_key
        self._tou_period = tou_period
        self._meter_type = meter_type
        
        # State tracking
        self._total_cost = 0.0
        self._last_consumption = None
        self._last_rate = None
        self._tracking_unsub = None
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
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id_suffix}"
        self._attr_has_entity_name = True
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{provider_name} {state_name}",
            "manufacturer": provider_name,
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }
    
    @property
    def native_value(self) -> StateType:
        """Return the current accumulated cost."""
        return self._total_cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Try to find current source meter entity
        current_source = self._find_source_meter()
        
        attrs = {
            "source_meter": current_source.entity_id if current_source else self._source_meter_entity,
            "last_consumption": self._last_consumption,
            "last_rate": self._last_rate,
        }
        
        if self._tou_period:
            attrs["tou_period"] = self._tou_period
        
        if self._rate_key:
            attrs["rate_type"] = self._rate_key
        
        return attrs
    
    def _find_source_meter(self):
        """Find the source meter dynamically."""
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        for meter in meters:
            # Match based on meter type and TOU period
            if hasattr(meter, '_meter_type') and meter._meter_type == self._meter_type:
                if self._tou_period:
                    # For TOU, match the period
                    if hasattr(meter, '_tou_period') and meter._tou_period == self._tou_period:
                        return meter
                else:
                    # For non-TOU, match total cycle
                    if hasattr(meter, '_cycle') and meter._cycle == "total":
                        return meter
        
        return None
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._total_cost = float(last_state.state)
                    _LOGGER.info(
                        "Restored cost meter %s: $%.2f",
                        self._attr_name,
                        self._total_cost
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore state for %s: %s",
                        self._attr_name,
                        last_state.state
                    )
                    self._total_cost = 0.0
            
            # Restore attributes
            if last_state.attributes:
                self._last_consumption = last_state.attributes.get("last_consumption")
                self._last_rate = last_state.attributes.get("last_rate")
        
        # Try to find and track the source meter
        self._setup_tracking()
        
        # Also track coordinator updates for rate changes
        self._coordinator.async_add_listener(self._handle_rate_update)
    
    def _setup_tracking(self) -> None:
        """Set up tracking for the source meter."""
        # Clean up existing tracking
        if self._tracking_unsub:
            self._tracking_unsub()
            self._tracking_unsub = None
        
        # Find the current source meter
        source_meter = self._find_source_meter()
        if source_meter:
            self._source_meter_entity = source_meter.entity_id
            self._tracking_unsub = async_track_state_change_event(
                self.hass,
                self._source_meter_entity,
                self._handle_consumption_change
            )
            _LOGGER.debug("Cost meter %s tracking source: %s", self._attr_name, self._source_meter_entity)
            
            # Get initial consumption value if we don't have one
            if self._last_consumption is None and source_meter.native_value is not None:
                try:
                    self._last_consumption = float(source_meter.native_value)
                    _LOGGER.info(
                        "%s: Initial consumption from setup: %.3f kWh",
                        self._attr_name,
                        self._last_consumption
                    )
                except (ValueError, TypeError):
                    pass
        else:
            _LOGGER.warning("Cost meter %s could not find source meter", self._attr_name)
            # Try again in 5 seconds
            self.hass.loop.call_later(5, lambda: self.hass.async_create_task(self._retry_setup()))
    
    async def _retry_setup(self) -> None:
        """Retry setting up tracking."""
        self._setup_tracking()
        if self._tracking_unsub:
            # Successfully found meter, get initial value
            source_meter = self._find_source_meter()
            if source_meter and source_meter.native_value is not None:
                try:
                    initial_consumption = float(source_meter.native_value)
                    if self._last_consumption is None:
                        self._last_consumption = initial_consumption
                        _LOGGER.info(
                            "%s: Got initial consumption from retry: %.3f kWh",
                            self._attr_name,
                            initial_consumption
                        )
                except (ValueError, TypeError):
                    pass
            # Update state
            self.async_write_ha_state()
    
    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        if self._tracking_unsub:
            self._tracking_unsub()
            self._tracking_unsub = None
        
        self._coordinator.async_remove_listener(self._handle_rate_update)
    
    @callback
    def _handle_rate_update(self) -> None:
        """Handle rate updates from coordinator."""
        # Check if we need to setup tracking (in case meters were just created)
        if not self._tracking_unsub:
            self._setup_tracking()
        # Just trigger an update - we'll check rates when consumption changes
        self.async_write_ha_state()
    
    async def _handle_consumption_change(self, event: Event) -> None:
        """Handle changes in consumption from source meter."""
        new_state: State = event.data.get("new_state")
        old_state: State = event.data.get("old_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        try:
            new_consumption = float(new_state.state)
        except (ValueError, TypeError):
            return
        
        # Get current rate based on configuration
        current_rate = self._get_current_rate()
        if current_rate is None or current_rate <= 0:
            _LOGGER.debug("No valid rate available for cost calculation")
            return
        
        # Calculate incremental cost if we have previous consumption
        if self._last_consumption is not None:
            consumption_delta = new_consumption - self._last_consumption
            
            # Only calculate cost for positive consumption changes
            if consumption_delta > 0:
                incremental_cost = consumption_delta * current_rate
                self._total_cost += incremental_cost
                
                _LOGGER.debug(
                    "%s: Consumption increased by %.3f kWh @ $%.5f/kWh = $%.2f (total: $%.2f)",
                    self._attr_name,
                    consumption_delta,
                    current_rate,
                    incremental_cost,
                    self._total_cost
                )
        else:
            # First reading - initialize but don't add cost
            _LOGGER.info(
                "%s: Initial consumption reading: %.3f kWh @ $%.5f/kWh",
                self._attr_name,
                new_consumption,
                current_rate
            )
        
        # Update tracking
        self._last_consumption = new_consumption
        self._last_rate = current_rate
        
        # Update state
        self.async_write_ha_state()
    
    def _get_current_rate(self) -> float | None:
        """Get the current rate based on configuration."""
        if not self._coordinator.data:
            return None
        
        if self._tou_period:
            # TOU rate based on period
            all_rates = self._coordinator.data.get("all_current_rates", {})
            tou_rates = all_rates.get("tou_rates", {})
            return tou_rates.get(self._tou_period, 0.0)
        elif self._rate_key:
            # Specific rate type
            all_rates = self._coordinator.data.get("all_current_rates", {})
            return all_rates.get(self._rate_key, 0.0)
        else:
            # Default current rate
            return self._coordinator.data.get("current_rate", 0.0)
    
    async def async_reset(self) -> None:
        """Reset the cost meter."""
        _LOGGER.info("Resetting cost meter: %s", self._attr_name)
        self._total_cost = 0.0
        self._last_consumption = None
        self._last_rate = None
        self.async_write_ha_state()


class UtilityTOUPeakCostMeter(UtilityTariffCostMeter):
    """Cost meter for peak period costs."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, coordinator):
        """Initialize the peak cost meter."""
        # Find the peak consumption meter
        meters = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("utility_meters", [])
        peak_meter = None
        
        for meter in meters:
            if (hasattr(meter, '_tou_period') and 
                meter._tou_period == "peak" and 
                meter._meter_type == "energy_delivered"):
                peak_meter = meter
                break
        
        if not peak_meter:
            raise ValueError("Peak consumption meter not found")
        
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            source_meter_entity=peak_meter.entity_id,
            coordinator=coordinator,
            name="Peak Period Cost",
            unique_id_suffix="tou_peak_cost_meter",
            tou_period="peak",
            meter_type="energy_delivered"
        )


class UtilityTOUShoulderCostMeter(UtilityTariffCostMeter):
    """Cost meter for shoulder period costs."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, coordinator):
        """Initialize the shoulder cost meter."""
        # Find the shoulder consumption meter
        meters = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("utility_meters", [])
        shoulder_meter = None
        
        for meter in meters:
            if (hasattr(meter, '_tou_period') and 
                meter._tou_period == "shoulder" and 
                meter._meter_type == "energy_delivered"):
                shoulder_meter = meter
                break
        
        if not shoulder_meter:
            raise ValueError("Shoulder consumption meter not found")
        
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            source_meter_entity=shoulder_meter.entity_id,
            coordinator=coordinator,
            name="Shoulder Period Cost",
            unique_id_suffix="tou_shoulder_cost_meter",
            tou_period="shoulder",
            meter_type="energy_delivered"
        )


class UtilityTOUOffPeakCostMeter(UtilityTariffCostMeter):
    """Cost meter for off-peak period costs."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, coordinator):
        """Initialize the off-peak cost meter."""
        # Find the off-peak consumption meter
        meters = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("utility_meters", [])
        off_peak_meter = None
        
        for meter in meters:
            if (hasattr(meter, '_tou_period') and 
                meter._tou_period == "off_peak" and 
                meter._meter_type == "energy_delivered"):
                off_peak_meter = meter
                break
        
        if not off_peak_meter:
            raise ValueError("Off-peak consumption meter not found")
        
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            source_meter_entity=off_peak_meter.entity_id,
            coordinator=coordinator,
            name="Off-Peak Period Cost",
            unique_id_suffix="tou_off_peak_cost_meter",
            tou_period="off_peak",
            meter_type="energy_delivered"
        )


class UtilityTotalEnergyCostMeter(UtilityTariffCostMeter):
    """Cost meter for total energy costs."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, coordinator):
        """Initialize the total cost meter."""
        # Check if TOU is enabled
        is_tou = "tou" in config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "")).lower()
        
        if is_tou:
            # For TOU, we need to track all three period cost meters and sum them
            # This will be handled differently - just placeholder for now
            raise NotImplementedError("TOU total cost meter needs special implementation")
        else:
            # Find the total consumption meter
            meters = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("utility_meters", [])
            total_meter = None
            
            for meter in meters:
                if (meter._meter_type == "energy_delivered" and 
                    meter._cycle == "total"):
                    total_meter = meter
                    break
            
            if not total_meter:
                raise ValueError("Total consumption meter not found")
            
            super().__init__(
                hass=hass,
                config_entry=config_entry,
                source_meter_entity=total_meter.entity_id,
                coordinator=coordinator,
                name="Total Energy Cost",
                unique_id_suffix="total_energy_cost_meter",
                rate_key="current_rate",
                meter_type="energy_delivered"
            )