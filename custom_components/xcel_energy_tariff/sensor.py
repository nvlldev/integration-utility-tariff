"""Enhanced sensor platform for Xcel Energy Tariff integration v2."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATES
from .coordinator import XcelDynamicCoordinator, XcelPDFCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xcel Energy Tariff sensors from a config entry."""
    pdf_coordinator = hass.data[DOMAIN][config_entry.entry_id]["pdf_coordinator"]
    dynamic_coordinator = hass.data[DOMAIN][config_entry.entry_id]["dynamic_coordinator"]
    tariff_manager = hass.data[DOMAIN][config_entry.entry_id]["tariff_manager"]
    
    sensors = []
    
    # Core rate sensors
    sensors.extend([
        XcelCurrentRateSensor(dynamic_coordinator, config_entry),
        XcelCurrentRateWithFeesSensor(dynamic_coordinator, config_entry),
        XcelBaseRateSensor(dynamic_coordinator, config_entry),
    ])
    
    # TOU sensors (if applicable)
    if "tou" in config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "")):
        sensors.extend([
            XcelTOUPeriodSensor(dynamic_coordinator, config_entry),
            XcelTimeUntilNextPeriodSensor(dynamic_coordinator, config_entry),
            XcelPeakRateSensor(dynamic_coordinator, config_entry),
            XcelShoulderRateSensor(dynamic_coordinator, config_entry),
            XcelOffPeakRateSensor(dynamic_coordinator, config_entry),
        ])
    
    # Cost projection sensors (if enabled)
    if config_entry.options.get("enable_cost_sensors", True):
        sensors.extend([
            XcelHourlyCostSensor(dynamic_coordinator, config_entry),
            XcelDailyCostSensor(dynamic_coordinator, config_entry),
            XcelMonthlyCostSensor(dynamic_coordinator, config_entry),
            XcelPredictedBillSensor(dynamic_coordinator, config_entry),
        ])
    
    # Status and info sensors
    sensors.extend([
        XcelDataSourceSensor(pdf_coordinator, config_entry),
        XcelLastUpdateSensor(pdf_coordinator, config_entry),
        XcelDataQualitySensor(pdf_coordinator, config_entry),
        XcelCurrentSeasonSensor(dynamic_coordinator, config_entry),
        XcelFixedChargeSensor(dynamic_coordinator, config_entry),
        XcelTotalAdditionalChargesSensor(dynamic_coordinator, config_entry),
        XcelEffectiveDateSensor(pdf_coordinator, config_entry),
    ])
    
    # Add all sensors
    async_add_entities(sensors)


class XcelSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Xcel Energy sensors."""
    
    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._key = key
        
        state = config_entry.data["state"]
        self._attr_name = f"Xcel {STATES[state]} {name}"
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Xcel Energy {STATES[state]}",
            "manufacturer": "Xcel Energy",
            "model": config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "residential")),
        }


class XcelCurrentRateSensor(XcelSensorBase):
    """Sensor for current electricity rate."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "current_rate", "Current Rate")
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


class XcelCurrentRateWithFeesSensor(XcelSensorBase):
    """Sensor for current rate including all fees."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "current_rate_with_fees", "Current Rate (with fees)")
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


class XcelBaseRateSensor(XcelSensorBase):
    """Sensor for base energy rate without fees."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "base_rate", "Base Energy Rate")
        self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/kWh"
        self._attr_suggested_display_precision = 4
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"
    
    @property
    def native_value(self) -> StateType:
        """Return the base rate."""
        return self.coordinator.data.get("current_rate")


class XcelTOUPeriodSensor(XcelSensorBase):
    """Sensor showing current TOU period."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "tou_period", "TOU Period")
        self._attr_icon = "mdi:clock-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the current period."""
        return self.coordinator.data.get("current_period", "Unknown")
    
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


class XcelTimeUntilNextPeriodSensor(XcelSensorBase):
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


class XcelPeakRateSensor(XcelSensorBase):
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


class XcelShoulderRateSensor(XcelSensorBase):
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


class XcelOffPeakRateSensor(XcelSensorBase):
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


class XcelHourlyCostSensor(XcelSensorBase):
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


class XcelDailyCostSensor(XcelSensorBase):
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


class XcelMonthlyCostSensor(XcelSensorBase):
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
            return costs.get("monthly_cost_estimate")
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
        else:
            attrs["average_daily_usage"] = self._config_entry.options.get("average_daily_usage", 30.0)
        return attrs


class XcelPredictedBillSensor(XcelSensorBase):
    """Sensor for predicted monthly bill based on current usage patterns."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "predicted_bill", "Predicted Monthly Bill")
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_suggested_display_precision = 2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd-circle-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the predicted monthly bill."""
        costs = self.coordinator.data.get("cost_projections", {})
        if not costs.get("available"):
            return None
            
        # Get current date info
        now = dt_util.now()
        days_in_month = 30  # Simplified, could be more accurate
        day_of_month = now.day
        days_remaining = days_in_month - day_of_month
        
        # Get current month-to-date cost
        daily_cost = costs.get("daily_cost_estimate", 0)
        fixed_monthly = costs.get("fixed_charges_monthly", 0)
        
        # Calculate month-to-date cost (approximate)
        mtd_cost = daily_cost * day_of_month
        
        # Calculate average daily cost over last 7 days (if available)
        # For now, use the current daily cost as average
        avg_daily_cost = daily_cost
        
        # Project remaining month
        projected_remaining = avg_daily_cost * days_remaining
        
        # Total predicted bill
        predicted_total = mtd_cost + projected_remaining + fixed_monthly
        
        return round(predicted_total, 2)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        costs = self.coordinator.data.get("cost_projections", {})
        now = dt_util.now()
        days_in_month = 30
        day_of_month = now.day
        days_remaining = days_in_month - day_of_month
        
        attrs = {
            "days_elapsed": day_of_month,
            "days_remaining": days_remaining,
            "billing_cycle_progress": f"{round((day_of_month / days_in_month) * 100)}%",
            "includes_fixed_charges": True,
            "prediction_method": "daily_average",
        }
        
        if costs.get("available"):
            daily_cost = costs.get("daily_cost_estimate", 0)
            attrs["month_to_date_estimate"] = round(daily_cost * day_of_month, 2)
            attrs["remaining_estimate"] = round(daily_cost * days_remaining, 2)
            attrs["fixed_charges"] = costs.get("fixed_charges_monthly", 0)
            attrs["consumption_source"] = costs.get("consumption_source", "manual")
            
        return attrs


class XcelDataSourceSensor(XcelSensorBase):
    """Sensor showing data source."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "data_source", "Data Source")
        self._attr_icon = "mdi:file-document-outline"
    
    @property
    def native_value(self) -> StateType:
        """Return the data source."""
        if self.coordinator.data.get("last_updated"):
            return "Xcel Energy PDF"
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


class XcelLastUpdateSensor(XcelSensorBase):
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


class XcelDataQualitySensor(XcelSensorBase):
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


class XcelCurrentSeasonSensor(XcelSensorBase):
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


class XcelFixedChargeSensor(XcelSensorBase):
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


class XcelTotalAdditionalChargesSensor(XcelSensorBase):
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


class XcelEffectiveDateSensor(XcelSensorBase):
    """Sensor showing tariff effective date."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "effective_date", "Tariff Effective Date")
        self._attr_icon = "mdi:calendar-check"
    
    @property
    def native_value(self) -> StateType:
        """Return the effective date."""
        return self.coordinator.data.get("effective_date", "Unknown")