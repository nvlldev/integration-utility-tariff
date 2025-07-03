"""Rate-related sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase


class UtilityCurrentRateSensor(UtilitySensorBase):
    """Sensor for current electricity rate."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "current_rate", "Current Rate")
        # Check service type for unit of measurement
        service_type = config_entry.data.get("service_type", "electric")
        if service_type == "gas":
            self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/therm"
        else:
            self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd"
    
    @property
    def native_value(self) -> StateType:
        """Return the current rate."""
        return self.coordinator.data.get("current_rate")
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "period": self.coordinator.data.get("current_period"),
            "season": self.coordinator.data.get("current_season"),
            "is_holiday": self.coordinator.data.get("is_holiday"),
            "is_weekend": self.coordinator.data.get("is_weekend"),
        }


class UtilityCurrentRateWithFeesSensor(UtilitySensorBase):
    """Sensor for current rate including all fees."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "current_rate_with_fees", "Current Rate With Fees")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd"
    
    @property
    def native_value(self) -> StateType:
        """Return the current rate with fees."""
        base_rate = self.coordinator.data.get("current_rate")
        if not base_rate:
            return None
            
        # Add additional charges
        all_rates = self.coordinator.data.get("all_current_rates", {})
        additional = all_rates.get("total_additional", 0)
        
        return base_rate + additional


class UtilityPeakRateSensor(UtilitySensorBase):
    """Sensor for peak TOU rate."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "peak_rate", "Peak Rate")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:trending-up"
    
    @property
    def native_value(self) -> StateType:
        """Return the peak rate."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        season = self.coordinator.data.get("current_season", "summer")
        return all_rates.get("tou_rates", {}).get("peak")


class UtilityShoulderRateSensor(UtilitySensorBase):
    """Sensor for shoulder TOU rate."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "shoulder_rate", "Shoulder Rate")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:trending-neutral"
    
    @property
    def native_value(self) -> StateType:
        """Return the shoulder rate."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        return all_rates.get("tou_rates", {}).get("shoulder")


class UtilityOffPeakRateSensor(UtilitySensorBase):
    """Sensor for off-peak TOU rate."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "off_peak_rate", "Off-Peak Rate")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:trending-down"
    
    @property
    def native_value(self) -> StateType:
        """Return the off-peak rate."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        return all_rates.get("tou_rates", {}).get("off_peak")