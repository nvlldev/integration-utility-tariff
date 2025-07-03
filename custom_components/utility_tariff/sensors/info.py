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
    
    @property
    def icon(self) -> str:
        """Return dynamic icon based on data source."""
        data_source = self.coordinator.data.get("data_source", "").lower()
        
        if data_source == "pdf":
            return "mdi:file-document-outline"
        elif data_source == "api":
            return "mdi:api"
        elif data_source == "fallback":
            return "mdi:database"
        elif data_source == "fallback_on_error":
            return "mdi:alert-circle-outline"
        elif data_source == "initializing":
            return "mdi:timer-sand"
        else:
            return "mdi:help-circle-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the data source."""
        # Check the data_source field in coordinator data
        data_source = self.coordinator.data.get("data_source", "").lower()
        provider = self.coordinator.hass.data[DOMAIN][self._config_entry.entry_id]["provider"]
        using_cache = self.coordinator.data.get("using_cache", False)
        
        if data_source == "pdf":
            pdf_source = self.coordinator.data.get("pdf_source", "downloaded")
            if pdf_source == "bundled":
                return f"{provider.name} PDF (Bundled)"
            elif using_cache:
                return f"{provider.name} PDF (Cached)"
            return f"{provider.name} PDF"
        elif data_source == "api":
            if using_cache:
                return f"{provider.name} API (Cached)"
            return f"{provider.name} API"
        elif data_source == "fallback":
            return f"{provider.name} Fallback"
        elif data_source == "fallback_on_error":
            return "Fallback (Error)"
        elif data_source == "initializing":
            return "Initializing"
        elif self.coordinator.data.get("last_updated"):
            # Legacy check - if we have data but no explicit source, assume PDF
            return f"{provider.name} PDF"
        else:
            return "No Data"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data_source = self.coordinator.data.get("data_source", "").lower()
        attrs = {
            "source_type": data_source or "unknown",
            "state": self._config_entry.data["state"],
        }
        
        # Add cache information if using cached data
        if self.coordinator.data.get("using_cache"):
            attrs.update({
                "using_cache": True,
                "cache_reason": self.coordinator.data.get("cache_reason", "Update failed"),
            })
        
        # Add source-specific attributes
        if data_source == "pdf":
            pdf_source = self.coordinator.data.get("pdf_source", "downloaded")
            attrs.update({
                "pdf_url": self.coordinator.data.get("pdf_url"),
                "pdf_hash": self.coordinator.data.get("pdf_hash"),
                "pdf_source": pdf_source,
                "extraction_method": self.coordinator.data.get("extraction_method", "pdf_parser"),
                "accuracy": "High - Direct from tariff document" if not attrs.get("using_cache") else "High - From cached tariff document",
            })
            
            # Add bundled PDF info if using bundled
            if pdf_source == "bundled":
                bundled_info = self.coordinator.data.get("bundled_pdf_info", {})
                attrs.update({
                    "bundled_version": bundled_info.get("version"),
                    "bundled_effective_date": bundled_info.get("effective_date"),
                    "bundled_filename": bundled_info.get("filename"),
                    "accuracy": "High - From bundled tariff document",
                })
        elif data_source == "api":
            attrs.update({
                "api_endpoint": self.coordinator.data.get("api_endpoint"),
                "api_version": self.coordinator.data.get("api_version"),
                "accuracy": "High - Real-time data",
            })
        elif data_source == "fallback":
            attrs.update({
                "accuracy": "Medium - Estimated rates",
                "effective_date": self.coordinator.data.get("effective_date", "Unknown"),
                "note": self.coordinator.data.get("note", "Using pre-configured fallback rates"),
            })
        elif data_source == "fallback_on_error":
            attrs.update({
                "accuracy": "Low - Error fallback",
                "error": self.coordinator.data.get("error", "Unknown error"),
                "last_successful_update": self.coordinator.data.get("pdf_last_successful"),
            })
        
        # Add last update time if available
        if self.coordinator.data.get("last_updated"):
            attrs["last_updated"] = self.coordinator.data.get("last_updated")
                
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