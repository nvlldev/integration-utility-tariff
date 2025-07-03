"""Cost calculation sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .base import UtilitySensorBase


class UtilityHourlyCostSensor(UtilitySensorBase):
    """Sensor for estimated hourly cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "hourly_cost", "Estimated Hourly Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-clock"
    
    @property
    def native_value(self) -> StateType:
        """Return the hourly cost."""
        costs = self.coordinator.data.get("cost_projections", {})
        if costs.get("available"):
            return costs.get("hourly_cost_estimate")
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        costs = self.coordinator.data.get("cost_projections", {})
        attrs = {}
        if costs.get("available"):
            attrs["consumption_source"] = costs.get("consumption_source", "manual")
            if costs.get("consumption_entity"):
                attrs["consumption_entity"] = costs.get("consumption_entity")
            attrs["daily_kwh_used"] = costs.get("daily_kwh_used")
        return attrs


class UtilityDailyCostSensor(UtilitySensorBase):
    """Sensor for estimated daily cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "daily_cost", "Estimated Daily Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:calendar-today"
    
    @property
    def native_value(self) -> StateType:
        """Return the daily cost."""
        costs = self.coordinator.data.get("cost_projections", {})
        if costs.get("available"):
            return costs.get("daily_cost_estimate")
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        costs = self.coordinator.data.get("cost_projections", {})
        attrs = {}
        if costs.get("available"):
            attrs["consumption_source"] = costs.get("consumption_source", "manual")
            if costs.get("consumption_entity"):
                attrs["consumption_entity"] = costs.get("consumption_entity")
            attrs["daily_kwh_used"] = costs.get("daily_kwh_used")
        return attrs


class UtilityMonthlyCostSensor(UtilitySensorBase):
    """Sensor for estimated monthly cost."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "monthly_cost", "Estimated Monthly Cost")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:calendar-month"
    
    @property
    def native_value(self) -> StateType:
        """Return the monthly cost."""
        costs = self.coordinator.data.get("cost_projections", {})
        if costs.get("available"):
            # Use the more accurate projected total cost if available
            return costs.get("projected_total_cost", costs.get("monthly_cost_estimate"))
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        costs = self.coordinator.data.get("cost_projections", {})
        attrs = {
            "includes_fixed_charges": True,
            "fixed_charges": costs.get("fixed_charges_monthly", 0),
        }
        if costs.get("available"):
            attrs["consumption_source"] = costs.get("consumption_source", "manual")
            if costs.get("consumption_entity"):
                attrs["consumption_entity"] = costs.get("consumption_entity")
            attrs["daily_kwh_used"] = costs.get("daily_kwh_used")
            # Add enhanced monthly projection data
            attrs["days_in_month"] = costs.get("days_in_month", 30)
            attrs["day_of_month"] = costs.get("day_of_month")
            attrs["days_remaining"] = costs.get("days_remaining")
            attrs["billing_cycle_progress"] = f"{costs.get('billing_cycle_progress', 0)}%"
            attrs["month_to_date_cost"] = costs.get("month_to_date_cost")
            attrs["projected_remaining_cost"] = costs.get("projected_remaining_cost")
            attrs["projection_method"] = "daily_average"
        else:
            attrs["average_daily_usage"] = self._config_entry.options.get("average_daily_usage", 30.0)
        return attrs


