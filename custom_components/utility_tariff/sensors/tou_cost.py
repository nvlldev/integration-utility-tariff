"""Time-of-Use cost sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase
from ..const import DOMAIN

class UtilityTOUPeakCostSensor(UtilitySensorBase):
    """Sensor for peak period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_peak_cost", "Peak Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
    
    @property
    def native_value(self) -> StateType:
        """Return the peak period cost."""
        # Get peak consumption from utility meters
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        peak_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "peak" and meter._meter_type == "energy_delivered":
                peak_consumption = meter.native_value or 0.0
                break
        
        # Get peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        peak_rate = all_rates.get("peak", 0.0)
        
        # Calculate cost
        return peak_consumption * peak_rate
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        peak_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "peak" and meter._meter_type == "energy_delivered":
                peak_consumption = meter.native_value or 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        peak_rate = all_rates.get("peak", 0.0)
        
        return {
            "period": "peak",
            "consumption_kwh": peak_consumption,
            "rate_per_kwh": peak_rate,
        }


class UtilityTOUShoulderCostSensor(UtilitySensorBase):
    """Sensor for shoulder period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_shoulder_cost", "Shoulder Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
    
    @property
    def native_value(self) -> StateType:
        """Return the shoulder period cost."""
        # Get shoulder consumption from utility meters
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        shoulder_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "shoulder" and meter._meter_type == "energy_delivered":
                shoulder_consumption = meter.native_value or 0.0
                break
        
        # Get shoulder rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        shoulder_rate = all_rates.get("shoulder", 0.0)
        
        # Calculate cost
        return shoulder_consumption * shoulder_rate
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        shoulder_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "shoulder" and meter._meter_type == "energy_delivered":
                shoulder_consumption = meter.native_value or 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        shoulder_rate = all_rates.get("shoulder", 0.0)
        
        return {
            "period": "shoulder",
            "consumption_kwh": shoulder_consumption,
            "rate_per_kwh": shoulder_rate,
        }


class UtilityTOUOffPeakCostSensor(UtilitySensorBase):
    """Sensor for off-peak period cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_off_peak_cost", "Off-Peak Period Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-clock"
    
    @property
    def native_value(self) -> StateType:
        """Return the off-peak period cost."""
        # Get off-peak consumption from utility meters
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        off_peak_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "off_peak" and meter._meter_type == "energy_delivered":
                off_peak_consumption = meter.native_value or 0.0
                break
        
        # Get off-peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        off_peak_rate = all_rates.get("off-peak", 0.0)
        
        # Calculate cost
        return off_peak_consumption * off_peak_rate
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        off_peak_consumption = 0.0
        
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "off_peak" and meter._meter_type == "energy_delivered":
                off_peak_consumption = meter.native_value or 0.0
                break
        
        all_rates = self.coordinator.data.get("all_current_rates", {})
        off_peak_rate = all_rates.get("off-peak", 0.0)
        
        return {
            "period": "off_peak",
            "consumption_kwh": off_peak_consumption,
            "rate_per_kwh": off_peak_rate,
        }


class UtilityTotalEnergyCostSensor(UtilitySensorBase):
    """Sensor for total energy cost across all periods."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "total_energy_cost", "Total Energy Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:cash-multiple"
    
    @property
    def native_value(self) -> StateType:
        """Return the total energy cost."""
        # Check if TOU is enabled
        is_tou = "tou" in self._config_entry.options.get("rate_schedule", self._config_entry.data.get("rate_schedule", "")).lower()
        
        if is_tou:
            # Sum up all TOU period costs
            peak_cost = 0.0
            shoulder_cost = 0.0
            off_peak_cost = 0.0
            
            # Get consumption from utility meters
            meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
            all_rates = self.coordinator.data.get("all_current_rates", {})
            
            for meter in meters:
                if hasattr(meter, '_tou_period') and meter._meter_type == "energy_delivered":
                    consumption = meter.native_value or 0.0
                    if meter._tou_period == "peak":
                        peak_cost = consumption * all_rates.get("peak", 0.0)
                    elif meter._tou_period == "shoulder":
                        shoulder_cost = consumption * all_rates.get("shoulder", 0.0)
                    elif meter._tou_period == "off_peak":
                        off_peak_cost = consumption * all_rates.get("off-peak", 0.0)
            
            return peak_cost + shoulder_cost + off_peak_cost
        else:
            # Non-TOU: simple calculation
            meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
            total_consumption = 0.0
            
            for meter in meters:
                if meter._meter_type == "energy_delivered" and meter._cycle == "total":
                    total_consumption = meter.native_value or 0.0
                    break
            
            current_rate = self.coordinator.data.get("current_rate", 0.0)
            return total_consumption * current_rate
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        is_tou = "tou" in self._config_entry.options.get("rate_schedule", self._config_entry.data.get("rate_schedule", "")).lower()
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        if is_tou:
            # Get individual period consumption and costs
            all_rates = self.coordinator.data.get("all_current_rates", {})
            period_data = {}
            total_consumption = 0.0
            
            for meter in meters:
                if hasattr(meter, '_tou_period') and meter._meter_type == "energy_delivered":
                    consumption = meter.native_value or 0.0
                    period = meter._tou_period
                    rate = all_rates.get(period.replace("_", "-"), 0.0)
                    cost = consumption * rate
                    
                    period_data[f"{period}_consumption_kwh"] = consumption
                    period_data[f"{period}_rate"] = rate
                    period_data[f"{period}_cost"] = cost
                    total_consumption += consumption
            
            period_data["total_consumption_kwh"] = total_consumption
            period_data["is_tou"] = True
            return period_data
        else:
            # Non-TOU attributes
            total_consumption = 0.0
            for meter in meters:
                if meter._meter_type == "energy_delivered" and meter._cycle == "total":
                    total_consumption = meter.native_value or 0.0
                    break
            
            current_rate = self.coordinator.data.get("current_rate", 0.0)
            
            return {
                "total_consumption_kwh": total_consumption,
                "current_rate": current_rate,
                "is_tou": False
            }