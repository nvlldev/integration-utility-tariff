"""Time-of-Use sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase


class UtilityTOUPeriodSensor(UtilitySensorBase):
    """Sensor showing current TOU period."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_period", "TOU Period")
        self._attr_icon = "mdi:clock-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the current period."""
        period = self.coordinator.data.get("current_period")
        return period if period is not None else "Unknown"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        tou_rates = all_rates.get("tou_rates", {})
        
        return {
            "peak_rate": tou_rates.get("peak"),
            "shoulder_rate": tou_rates.get("shoulder"),
            "off_peak_rate": tou_rates.get("off_peak"),
            "schedule": self.coordinator.data.get("tou_schedule", {}),
        }


class UtilityTimeUntilNextPeriodSensor(UtilitySensorBase):
    """Sensor showing time until next TOU period change."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "time_until_next_period", "Time Until Next Period")
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer-sand"
    
    @property
    def native_value(self) -> StateType:
        """Return minutes until next period."""
        next_period = self.coordinator.data.get("next_period_change", {})
        if next_period.get("available"):
            return next_period.get("minutes_until")
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        next_period = self.coordinator.data.get("next_period_change", {})
        if next_period.get("available"):
            return {
                "next_period": next_period.get("next_period"),
                "next_change_time": next_period.get("next_change"),
            }
        return {}