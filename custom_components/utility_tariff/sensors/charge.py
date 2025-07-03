"""Charge-related sensors for Utility Tariff integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.typing import StateType

from .base import UtilitySensorBase


class UtilityFixedChargeSensor(UtilitySensorBase):
    """Sensor for fixed monthly charge."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "fixed_charge", "Monthly Service Charge")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd"
    
    @property
    def native_value(self) -> StateType:
        """Return the fixed charge."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        charges = all_rates.get("fixed_charges", {})
        return charges.get("monthly_service")


class UtilityTotalAdditionalChargesSensor(UtilitySensorBase):
    """Sensor for total additional charges per kWh."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "total_additional_charges", "Additional Charges")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 5
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:plus-circle-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return total additional charges."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        return all_rates.get("total_additional", 0)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown of charges."""
        all_rates = self.coordinator.data.get("all_current_rates", {})
        charges = all_rates.get("additional_charges", {})
        
        attrs = {}
        for charge_type, amount in charges.items():
            attrs[charge_type] = f"${amount:.5f}/kWh"
            
        return attrs