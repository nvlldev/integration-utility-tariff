"""Time-of-Use cost sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import RestoreEntity, SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase
from ..const import DOMAIN

class UtilityTOUPeakCostSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for peak period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_peak_cost", "Peak Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
        self._last_known_value = None
        self._last_known_consumption = None
        self._last_known_rate = None
    
    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._last_known_value = float(last_state.state)
                    # Restore consumption and rate from attributes
                    if last_state.attributes:
                        self._last_known_consumption = last_state.attributes.get("consumption_kwh", 0.0)
                        self._last_known_rate = last_state.attributes.get("rate_per_kwh", 0.0)
                except (ValueError, TypeError):
                    pass
    
    @property
    def native_value(self) -> StateType:
        """Return the peak period cost."""
        # Get peak consumption from utility meter entities
        peak_consumption = None
        meter_found = False
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "peak" and meter._meter_type == "energy_delivered":
                meter_found = True
                if meter.native_value is not None:
                    try:
                        peak_consumption = float(meter.native_value)
                        self._last_known_consumption = peak_consumption
                    except (ValueError, TypeError):
                        pass
                break
        
        # Get peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        peak_rate = tou_rates.get("peak", 0.0)
        
        if peak_rate > 0:
            self._last_known_rate = peak_rate
        
        # Use last known values if current data is not available
        if peak_consumption is None and self._last_known_consumption is not None:
            peak_consumption = self._last_known_consumption
        
        if peak_rate == 0.0 and self._last_known_rate is not None:
            peak_rate = self._last_known_rate
        
        # If we still don't have consumption data, return last known value
        if peak_consumption is None:
            return self._last_known_value
        
        # Calculate cost
        cost = (peak_consumption or 0.0) * peak_rate
        self._last_known_value = cost
        return cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Get peak consumption from utility meter entities
        peak_consumption = 0.0
        source_entity = None
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "peak" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        peak_consumption = float(meter.native_value)
                        source_entity = meter.entity_id
                    except (ValueError, TypeError):
                        peak_consumption = 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        peak_rate = tou_rates.get("peak", 0.0)
        
        return {
            "period": "peak",
            "consumption_kwh": peak_consumption,
            "rate_per_kwh": peak_rate,
            "source_entity": source_entity,
        }


class UtilityTOUShoulderCostSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for shoulder period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_shoulder_cost", "Shoulder Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
        self._last_known_value = None
        self._last_known_consumption = None
        self._last_known_rate = None
    
    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._last_known_value = float(last_state.state)
                    # Restore consumption and rate from attributes
                    if last_state.attributes:
                        self._last_known_consumption = last_state.attributes.get("consumption_kwh", 0.0)
                        self._last_known_rate = last_state.attributes.get("rate_per_kwh", 0.0)
                except (ValueError, TypeError):
                    pass
    
    @property
    def native_value(self) -> StateType:
        """Return the shoulder period cost."""
        # Get shoulder consumption from utility meter entities
        shoulder_consumption = None
        meter_found = False
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the shoulder period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "shoulder" and meter._meter_type == "energy_delivered":
                meter_found = True
                if meter.native_value is not None:
                    try:
                        shoulder_consumption = float(meter.native_value)
                        self._last_known_consumption = shoulder_consumption
                    except (ValueError, TypeError):
                        pass
                break
        
        # Get shoulder rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        shoulder_rate = tou_rates.get("shoulder", 0.0)
        
        if shoulder_rate > 0:
            self._last_known_rate = shoulder_rate
        
        # Use last known values if current data is not available
        if shoulder_consumption is None and self._last_known_consumption is not None:
            shoulder_consumption = self._last_known_consumption
        
        if shoulder_rate == 0.0 and self._last_known_rate is not None:
            shoulder_rate = self._last_known_rate
        
        # If we still don't have consumption data, return last known value
        if shoulder_consumption is None:
            return self._last_known_value
        
        # Calculate cost
        cost = (shoulder_consumption or 0.0) * shoulder_rate
        self._last_known_value = cost
        return cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Get shoulder consumption from utility meter entities
        shoulder_consumption = 0.0
        source_entity = None
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the shoulder period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "shoulder" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        shoulder_consumption = float(meter.native_value)
                        source_entity = meter.entity_id
                    except (ValueError, TypeError):
                        shoulder_consumption = 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        shoulder_rate = tou_rates.get("shoulder", 0.0)
        
        return {
            "period": "shoulder",
            "consumption_kwh": shoulder_consumption,
            "rate_per_kwh": shoulder_rate,
            "source_entity": source_entity,
        }


class UtilityTOUOffPeakCostSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for off-peak period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_off_peak_cost", "Off-Peak Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
        self._last_known_value = None
        self._last_known_consumption = None
        self._last_known_rate = None
    
    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._last_known_value = float(last_state.state)
                    # Restore consumption and rate from attributes
                    if last_state.attributes:
                        self._last_known_consumption = last_state.attributes.get("consumption_kwh", 0.0)
                        self._last_known_rate = last_state.attributes.get("rate_per_kwh", 0.0)
                except (ValueError, TypeError):
                    pass
    
    @property
    def native_value(self) -> StateType:
        """Return the off-peak period cost."""
        # Get off-peak consumption from utility meter entities
        off_peak_consumption = None
        meter_found = False
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the off-peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "off_peak" and meter._meter_type == "energy_delivered":
                meter_found = True
                if meter.native_value is not None:
                    try:
                        off_peak_consumption = float(meter.native_value)
                        self._last_known_consumption = off_peak_consumption
                    except (ValueError, TypeError):
                        pass
                break
        
        # Get off-peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        off_peak_rate = tou_rates.get("off_peak", 0.0)
        
        if off_peak_rate > 0:
            self._last_known_rate = off_peak_rate
        
        # Use last known values if current data is not available
        if off_peak_consumption is None and self._last_known_consumption is not None:
            off_peak_consumption = self._last_known_consumption
        
        if off_peak_rate == 0.0 and self._last_known_rate is not None:
            off_peak_rate = self._last_known_rate
        
        # If we still don't have consumption data, return last known value
        if off_peak_consumption is None:
            return self._last_known_value
        
        # Calculate cost
        cost = (off_peak_consumption or 0.0) * off_peak_rate
        self._last_known_value = cost
        return cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Get off-peak consumption from utility meter entities
        off_peak_consumption = 0.0
        source_entity = None
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the off-peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "off_peak" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        off_peak_consumption = float(meter.native_value)
                        source_entity = meter.entity_id
                    except (ValueError, TypeError):
                        off_peak_consumption = 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        off_peak_rate = tou_rates.get("off_peak", 0.0)
        
        return {
            "period": "off_peak",
            "consumption_kwh": off_peak_consumption,
            "rate_per_kwh": off_peak_rate,
            "source_entity": source_entity,
        }


class UtilityTotalEnergyCostSensor(UtilitySensorBase, RestoreEntity):
    """Sensor for total energy cost across all periods."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "total_energy_cost", "Total Energy Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-multiple"
        self._last_known_value = None
        self._last_known_consumption_by_period = {}
        self._last_known_rates = {}
    
    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._last_known_value = float(last_state.state)
                    # Restore period data from attributes
                    if last_state.attributes:
                        for period in ["peak", "shoulder", "off_peak"]:
                            consumption_key = f"{period}_consumption_kwh"
                            rate_key = f"{period}_rate"
                            if consumption_key in last_state.attributes:
                                self._last_known_consumption_by_period[period] = last_state.attributes[consumption_key]
                            if rate_key in last_state.attributes:
                                self._last_known_rates[period] = last_state.attributes[rate_key]
                except (ValueError, TypeError):
                    pass
    
    @property
    def native_value(self) -> StateType:
        """Return the total energy cost."""
        # Check if TOU is enabled
        is_tou = "tou" in self._config_entry.options.get("rate_schedule", self._config_entry.data.get("rate_schedule", "")).lower()
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        if is_tou:
            # Sum up all TOU period costs
            total_cost = 0.0
            has_any_data = False
            
            # Get rates
            all_rates = self.coordinator.data.get("all_current_rates", {})
            tou_rates = all_rates.get("tou_rates", {})
            
            # Update last known rates if we have new ones
            for period in ["peak", "shoulder", "off_peak"]:
                if period in tou_rates and tou_rates[period] > 0:
                    self._last_known_rates[period] = tou_rates[period]
            
            # Get consumption from each period's meter
            current_consumption = {}
            for meter in meters:
                if hasattr(meter, '_tou_period') and meter._meter_type == "energy_delivered":
                    period = meter._tou_period
                    if meter.native_value is not None:
                        try:
                            consumption = float(meter.native_value)
                            current_consumption[period] = consumption
                            self._last_known_consumption_by_period[period] = consumption
                            has_any_data = True
                        except (ValueError, TypeError):
                            pass
            
            # Calculate total cost using current or last known values
            for period in ["peak", "shoulder", "off_peak"]:
                consumption = current_consumption.get(period)
                if consumption is None:
                    consumption = self._last_known_consumption_by_period.get(period, 0.0)
                
                rate = tou_rates.get(period, 0.0)
                if rate == 0.0:
                    rate = self._last_known_rates.get(period, 0.0)
                
                total_cost += consumption * rate
            
            # If we have no data at all, return last known value
            if not has_any_data and not current_consumption and self._last_known_value is not None:
                return self._last_known_value
            
            self._last_known_value = total_cost
            return total_cost
        else:
            # Non-TOU: simple calculation
            total_consumption = None
            
            # Look for the total energy delivered meter
            for meter in meters:
                if meter._meter_type == "energy_delivered" and meter._cycle == "total":
                    if meter.native_value is not None:
                        try:
                            total_consumption = float(meter.native_value)
                            self._last_known_consumption_by_period["total"] = total_consumption
                        except (ValueError, TypeError):
                            pass
                    break
            
            current_rate = self.coordinator.data.get("current_rate", 0.0)
            if current_rate > 0:
                self._last_known_rates["standard"] = current_rate
            elif "standard" in self._last_known_rates:
                current_rate = self._last_known_rates["standard"]
            
            # Use last known consumption if current is not available
            if total_consumption is None:
                total_consumption = self._last_known_consumption_by_period.get("total", 0.0)
            
            cost = total_consumption * current_rate
            self._last_known_value = cost
            return cost
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        is_tou = "tou" in self._config_entry.options.get("rate_schedule", self._config_entry.data.get("rate_schedule", "")).lower()
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        if is_tou:
            # Get individual period consumption and costs
            all_rates = self.coordinator.data.get("all_current_rates", {})
            tou_rates = all_rates.get("tou_rates", {})
            period_data = {}
            total_consumption = 0.0
            
            # Get consumption from meter entities
            period_consumptions = {"peak": 0.0, "shoulder": 0.0, "off_peak": 0.0}
            
            for meter in meters:
                if hasattr(meter, '_tou_period') and meter._meter_type == "energy_delivered":
                    period = meter._tou_period
                    if meter.native_value is not None:
                        try:
                            period_consumptions[period] = float(meter.native_value)
                        except (ValueError, TypeError):
                            pass
            
            # Peak
            peak_consumption = period_consumptions.get("peak", 0.0)
            period_data["peak_consumption_kwh"] = peak_consumption
            period_data["peak_rate"] = tou_rates.get("peak", 0.0)
            period_data["peak_cost"] = peak_consumption * tou_rates.get("peak", 0.0)
            total_consumption += peak_consumption
            
            # Shoulder
            shoulder_consumption = period_consumptions.get("shoulder", 0.0)
            period_data["shoulder_consumption_kwh"] = shoulder_consumption
            period_data["shoulder_rate"] = tou_rates.get("shoulder", 0.0)
            period_data["shoulder_cost"] = shoulder_consumption * tou_rates.get("shoulder", 0.0)
            total_consumption += shoulder_consumption
            
            # Off-peak
            off_peak_consumption = period_consumptions.get("off_peak", 0.0)
            period_data["off_peak_consumption_kwh"] = off_peak_consumption
            period_data["off_peak_rate"] = tou_rates.get("off_peak", 0.0)
            period_data["off_peak_cost"] = off_peak_consumption * tou_rates.get("off_peak", 0.0)
            total_consumption += off_peak_consumption
            
            period_data["total_consumption_kwh"] = total_consumption
            period_data["is_tou"] = True
            return period_data
        else:
            # Non-TOU attributes
            total_consumption = 0.0
            
            # Look for the total energy delivered meter
            for meter in meters:
                if meter._meter_type == "energy_delivered" and meter._cycle == "total":
                    if meter.native_value is not None:
                        try:
                            total_consumption = float(meter.native_value)
                        except (ValueError, TypeError):
                            total_consumption = 0.0
                    break
            
            current_rate = self.coordinator.data.get("current_rate", 0.0)
            
            return {
                "total_consumption_kwh": total_consumption,
                "current_rate": current_rate,
                "is_tou": False
            }