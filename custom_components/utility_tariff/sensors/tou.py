"""Time-of-Use sensors for Utility Tariff integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
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
        super().__init__(coordinator, config_entry, "time_until_next_period", "Next Period Change")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:timer-sand"
    
    @property
    def native_value(self) -> StateType:
        """Return the timestamp of next period change."""
        next_period = self.coordinator.data.get("next_period_change", {})
        if next_period.get("available") and next_period.get("next_change"):
            # The coordinator provides ISO format timestamp
            try:
                return next_period.get("next_change")
            except:
                return None
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        next_period = self.coordinator.data.get("next_period_change", {})
        if next_period.get("available"):
            attrs = {
                "next_period": next_period.get("next_period"),
            }
            # Include minutes until for backward compatibility
            if next_period.get("minutes_until") is not None:
                attrs["minutes_until"] = next_period.get("minutes_until")
            return attrs
        return {}