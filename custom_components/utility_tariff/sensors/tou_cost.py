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
    
    @property
    def native_value(self) -> StateType:
        """Return the peak period cost."""
        # Get peak consumption from utility meter entities
        peak_consumption = 0.0
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "peak" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        peak_consumption = float(meter.native_value)
                    except (ValueError, TypeError):
                        peak_consumption = 0.0
                break
        
        # Get peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        peak_rate = tou_rates.get("peak", 0.0)
        
        # Calculate cost
        return peak_consumption * peak_rate
    
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
    
    @property
    def native_value(self) -> StateType:
        """Return the shoulder period cost."""
        # Get shoulder consumption from utility meter entities
        shoulder_consumption = 0.0
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the shoulder period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "shoulder" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        shoulder_consumption = float(meter.native_value)
                    except (ValueError, TypeError):
                        shoulder_consumption = 0.0
                break
        
        # Get shoulder rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        shoulder_rate = tou_rates.get("shoulder", 0.0)
        
        # Calculate cost
        return shoulder_consumption * shoulder_rate
    
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
    
    @property
    def native_value(self) -> StateType:
        """Return the off-peak period cost."""
        # Get off-peak consumption from utility meter entities
        off_peak_consumption = 0.0
        
        # Get the utility meters from the integration data
        meters = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {}).get("utility_meters", [])
        
        # Find the off-peak period energy delivered meter
        for meter in meters:
            if hasattr(meter, '_tou_period') and meter._tou_period == "off_peak" and meter._meter_type == "energy_delivered":
                if meter.native_value is not None:
                    try:
                        off_peak_consumption = float(meter.native_value)
                    except (ValueError, TypeError):
                        off_peak_consumption = 0.0
                break
        
        # Get off-peak rate
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        off_peak_rate = tou_rates.get("off_peak", 0.0)
        
        # Calculate cost
        return off_peak_consumption * off_peak_rate
    
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
            
            # Get rates
            all_rates = self.coordinator.data.get("all_current_rates", {})
            tou_rates = all_rates.get("tou_rates", {})
            
            # Get consumption from each period's meter
            for meter in meters:
                if hasattr(meter, '_tou_period') and meter._meter_type == "energy_delivered":
                    period = meter._tou_period
                    if meter.native_value is not None:
                        try:
                            consumption = float(meter.native_value)
                            rate = tou_rates.get(period, 0.0)
                            total_cost += consumption * rate
                        except (ValueError, TypeError):
                            pass
            
            return total_cost
        else:
            # Non-TOU: simple calculation
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
            return total_consumption * current_rate
    
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