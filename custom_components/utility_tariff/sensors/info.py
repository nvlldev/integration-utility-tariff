"""Informational sensors for Utility Tariff integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.typing import StateType

from ..const import DOMAIN
from .base import UtilitySensorBase


class UtilityDataSourceSensor(UtilitySensorBase):
    """Sensor showing data source."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "data_source", "Data Source")
        self._attr_icon = "mdi:file-document-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the data source."""
        if self.coordinator.data.get("last_updated"):
            provider = self.coordinator.hass.data[DOMAIN][self._config_entry.entry_id]["provider"]
            return f"{provider.name} PDF"
        return "Fallback Rates"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "source": self.native_value,
            "state": self._config_entry.data["state"],
        }
        
        if self.coordinator.data.get("last_updated"):
            attrs.update({
                "pdf_url": self.coordinator.data.get("pdf_url"),
                "pdf_hash": self.coordinator.data.get("pdf_hash"),
                "extraction_method": self.coordinator.data.get("extraction_method"),
            })
        else:
            if self._config_entry.data["state"] == "CO":
                attrs["accuracy"] = "High - Based on actual PDF extraction"
            else:
                attrs["accuracy"] = "Medium - Estimated rates"
                
        return attrs


class UtilityLastUpdateSensor(UtilitySensorBase):
    """Sensor showing last update time."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "last_update", "Last Update")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:update"
    
    @property
    def native_value(self) -> StateType:
        """Return the last update time."""
        timestamp_str = self.coordinator.data.get("pdf_last_successful")
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                return None
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "last_check": self.coordinator.data.get("pdf_last_checked"),
            "update_frequency": self._config_entry.options.get("update_frequency", "weekly"),
        }


class UtilityDataQualitySensor(UtilitySensorBase):
    """Sensor showing data quality score."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "data_quality", "Data Quality")
        self._attr_native_unit_of_measurement = "%"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:quality-high"
    
    @property
    def native_value(self) -> StateType:
        """Return the data quality score."""
        if not self.coordinator.data:
            return 0
            
        # Calculate quality based on extracted data
        score = 0
        max_score = 100
        
        # Check what was extracted
        if self.coordinator.data.get("rates"):
            score += 20
        if self.coordinator.data.get("tou_rates"):
            score += 20
        if self.coordinator.data.get("fixed_charges"):
            score += 15
        if self.coordinator.data.get("tou_schedule"):
            score += 15
        if self.coordinator.data.get("additional_charges"):
            score += 10
        if self.coordinator.data.get("rate_details"):
            score += 10
        if self.coordinator.data.get("effective_date"):
            score += 5
        if self.coordinator.data.get("season_definitions"):
            score += 5
            
        return score
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "has_base_rates": bool(self.coordinator.data.get("rates")),
            "has_tou_rates": bool(self.coordinator.data.get("tou_rates")),
            "has_fixed_charges": bool(self.coordinator.data.get("fixed_charges")),
            "has_schedule": bool(self.coordinator.data.get("tou_schedule")),
            "has_additional_charges": bool(self.coordinator.data.get("additional_charges")),
        }


class UtilityCurrentSeasonSensor(UtilitySensorBase):
    """Sensor showing current season."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "current_season", "Current Season")
        self._attr_icon = "mdi:weather-sunny"
    
    @property
    def native_value(self) -> StateType:
        """Return the current season."""
        return self.coordinator.data.get("current_season", "unknown").title()
    
    @property
    def icon(self) -> str:
        """Return dynamic icon based on season."""
        if self.native_value == "Summer":
            return "mdi:weather-sunny"
        return "mdi:snowflake"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        # Get season definitions
        definitions = {}
        if self.coordinator.data.get("season_definitions"):
            definitions = self.coordinator.data["season_definitions"]
        else:
            # Use configured months
            summer_months = self._config_entry.options.get("summer_months", "6,7,8,9")
            definitions["configured_summer_months"] = summer_months
            
        return definitions


class UtilityEffectiveDateSensor(UtilitySensorBase):
    """Sensor showing tariff effective date."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "effective_date", "Tariff Effective Date")
        self._attr_icon = "mdi:calendar-check"
    
    @property
    def native_value(self) -> StateType:
        """Return the effective date."""
        return self.coordinator.data.get("effective_date", "Unknown")