"""Test cost calculation sensors."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from custom_components.utility_tariff.sensors.cost import (
    UtilityHourlyCostSensor,
    UtilityDailyCostSensor,
    UtilityMonthlyCostSensor,
    UtilityPredictedBillSensor,
)
from custom_components.utility_tariff.const import DOMAIN


class TestCostSensors:
    """Test cost sensor implementations."""
    
    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with cost data."""
        coordinator = Mock()
        coordinator.hass = Mock()
        coordinator.hass.data = {
            DOMAIN: {
                "test_entry": {
                    "provider": Mock(name="Test Provider")
                }
            }
        }
        coordinator.data = {
            "cost_projections": {
                "available": True,
                "hourly_cost_estimate": 0.50,
                "daily_cost_estimate": 12.00,
                "monthly_cost_estimate": 360.00,
                "fixed_charges_monthly": 15.00,
                "consumption_source": "entity_daily_consumption",
                "consumption_entity": "sensor.home_energy",
                "daily_kwh_used": 100
            }
        }
        return coordinator
    
    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"state": "CO"}
        entry.options = {"rate_schedule": "residential", "average_daily_usage": 30.0}
        return entry
    
    def test_hourly_cost_sensor(self, mock_coordinator, mock_config_entry):
        """Test hourly cost sensor."""
        sensor = UtilityHourlyCostSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Estimated Hourly Cost"
        assert sensor._attr_unique_id == "test_entry_hourly_cost"
        assert sensor._attr_native_unit_of_measurement == "$"
        assert sensor._attr_suggested_display_precision == 2
        assert sensor._attr_icon == "mdi:cash-clock"
        
        assert sensor.native_value == 0.50
        
        attrs = sensor.extra_state_attributes
        assert attrs["consumption_source"] == "entity_daily_consumption"
        assert attrs["consumption_entity"] == "sensor.home_energy"
        assert attrs["daily_kwh_used"] == 100
    
    def test_hourly_cost_not_available(self, mock_coordinator, mock_config_entry):
        """Test hourly cost when not available."""
        mock_coordinator.data["cost_projections"]["available"] = False
        sensor = UtilityHourlyCostSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}
    
    def test_daily_cost_sensor(self, mock_coordinator, mock_config_entry):
        """Test daily cost sensor."""
        sensor = UtilityDailyCostSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Estimated Daily Cost"
        assert sensor._attr_icon == "mdi:calendar-today"
        assert sensor.native_value == 12.00
    
    def test_monthly_cost_sensor(self, mock_coordinator, mock_config_entry):
        """Test monthly cost sensor."""
        sensor = UtilityMonthlyCostSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Estimated Monthly Cost"
        assert sensor._attr_icon == "mdi:calendar-month"
        assert sensor.native_value == 360.00
        
        attrs = sensor.extra_state_attributes
        assert attrs["includes_fixed_charges"] is True
        assert attrs["fixed_charges"] == 15.00
        assert attrs["consumption_source"] == "entity_daily_consumption"
        assert attrs["daily_kwh_used"] == 100
    
    def test_monthly_cost_sensor_manual_usage(self, mock_coordinator, mock_config_entry):
        """Test monthly cost sensor with manual usage."""
        mock_coordinator.data["cost_projections"]["available"] = False
        sensor = UtilityMonthlyCostSensor(mock_coordinator, mock_config_entry)
        
        attrs = sensor.extra_state_attributes
        assert attrs["average_daily_usage"] == 30.0
    
    @patch('custom_components.utility_tariff.sensors.cost.dt_util')
    def test_predicted_bill_sensor(self, mock_dt_util, mock_coordinator, mock_config_entry):
        """Test predicted bill sensor."""
        # Mock current date as day 15 of a 30-day month
        mock_now = datetime(2024, 1, 15, 12, 0, 0)
        mock_dt_util.now.return_value = mock_now
        
        sensor = UtilityPredictedBillSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Predicted Monthly Bill"
        assert sensor._attr_icon == "mdi:currency-usd-circle-outline"
        
        # Predicted: (12 * 15) + (12 * 15) + 15 = 180 + 180 + 15 = 375
        assert sensor.native_value == 375.00
        
        attrs = sensor.extra_state_attributes
        assert attrs["days_elapsed"] == 15
        assert attrs["days_remaining"] == 15
        assert attrs["billing_cycle_progress"] == "50%"
        assert attrs["includes_fixed_charges"] is True
        assert attrs["prediction_method"] == "daily_average"
        assert attrs["month_to_date_estimate"] == 180.00
        assert attrs["remaining_estimate"] == 180.00
        assert attrs["fixed_charges"] == 15.00
    
    @patch('custom_components.utility_tariff.sensors.cost.dt_util')
    def test_predicted_bill_no_data(self, mock_dt_util, mock_coordinator, mock_config_entry):
        """Test predicted bill when no cost data available."""
        mock_now = datetime(2024, 1, 15, 12, 0, 0)
        mock_dt_util.now.return_value = mock_now
        
        mock_coordinator.data["cost_projections"]["available"] = False
        sensor = UtilityPredictedBillSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value is None
        
        attrs = sensor.extra_state_attributes
        assert attrs["days_elapsed"] == 15
        assert attrs["days_remaining"] == 15
        assert "month_to_date_estimate" not in attrs
    
    @patch('custom_components.utility_tariff.sensors.cost.dt_util')
    def test_predicted_bill_end_of_month(self, mock_dt_util, mock_coordinator, mock_config_entry):
        """Test predicted bill at end of month."""
        # Mock current date as day 28 of a 30-day month
        mock_now = datetime(2024, 1, 28, 23, 59, 59)
        mock_dt_util.now.return_value = mock_now
        
        sensor = UtilityPredictedBillSensor(mock_coordinator, mock_config_entry)
        
        # Predicted: (12 * 28) + (12 * 2) + 15 = 336 + 24 + 15 = 375
        assert sensor.native_value == 375.00
        
        attrs = sensor.extra_state_attributes
        assert attrs["days_elapsed"] == 28
        assert attrs["days_remaining"] == 2
        assert attrs["billing_cycle_progress"] == "93%"