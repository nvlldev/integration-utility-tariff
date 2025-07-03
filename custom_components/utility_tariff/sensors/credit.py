"""Grid credit sensor for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase


class UtilityGridCreditSensor(UtilitySensorBase):
    """Sensor for estimated daily credit from excess solar export."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "grid_credit", "Daily Grid Credit")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-plus"
    
    @property
    def native_value(self) -> StateType:
        """Return the daily grid credit."""
        costs = self.coordinator.data.get("cost_projections", {})
        if costs.get("available"):
            return costs.get("daily_credit_estimate", 0)
        return 0
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        costs = self.coordinator.data.get("cost_projections", {})
        attrs = {}
        if costs.get("available"):
            excess_return = max(0, costs.get("daily_kwh_returned", 0) - costs.get("daily_kwh_consumed", 0))
            attrs["excess_export_kwh"] = excess_return
            attrs["export_rate"] = costs.get("per_kwh_now")
            attrs["monthly_credit_estimate"] = costs.get("daily_credit_estimate", 0) * 30
            attrs["return_source"] = costs.get("return_source")
            if costs.get("return_entity"):
                attrs["return_entity"] = costs.get("return_entity")
        return attrs