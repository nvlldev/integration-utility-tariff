"""Test predicted bill sensor."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.utility_tariff.sensors import UtilityPredictedBillSensor
from custom_components.utility_tariff.coordinator import DynamicCoordinator


async def test_predicted_bill_calculation():
    """Test predicted bill calculation."""
    # Mock coordinator data
    coordinator = MagicMock()
    coordinator.data = {
        "cost_projections": {
            "available": True,
            "daily_cost_estimate": 5.50,  # $5.50 per day
            "fixed_charges_monthly": 10.00,  # $10 monthly service charge
            "consumption_source": "entity_daily",
        }
    }
    
    # Mock config entry
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "CO"}
    
    # Create sensor
    sensor = UtilityPredictedBillSensor(coordinator, config_entry)
    
    # Test mid-month calculation (day 15 of 30)
    with patch("custom_components.utility_tariff.sensor.dt_util.now") as mock_now:
        mock_now.return_value = datetime(2024, 1, 15, 12, 0, 0)
        
        # Calculate predicted bill
        predicted = sensor.native_value
        
        # Expected: (5.50 * 15 days elapsed) + (5.50 * 15 days remaining) + 10 fixed
        # = 82.50 + 82.50 + 10 = 175.00
        assert predicted == 175.00
        
        # Check attributes
        attrs = sensor.extra_state_attributes
        assert attrs["days_elapsed"] == 15
        assert attrs["days_remaining"] == 15
        assert attrs["billing_cycle_progress"] == "50%"
        assert attrs["month_to_date_estimate"] == 82.50
        assert attrs["remaining_estimate"] == 82.50
        assert attrs["fixed_charges"] == 10.00


async def test_predicted_bill_early_month():
    """Test predicted bill early in the month."""
    coordinator = MagicMock()
    coordinator.data = {
        "cost_projections": {
            "available": True,
            "daily_cost_estimate": 4.00,
            "fixed_charges_monthly": 12.00,
        }
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "MN"}
    
    sensor = UtilityPredictedBillSensor(coordinator, config_entry)
    
    # Test on day 3 of the month
    with patch("custom_components.utility_tariff.sensor.dt_util.now") as mock_now:
        mock_now.return_value = datetime(2024, 2, 3, 8, 0, 0)
        
        predicted = sensor.native_value
        
        # Expected: (4.00 * 3) + (4.00 * 27) + 12 = 12 + 108 + 12 = 132
        assert predicted == 132.00
        
        attrs = sensor.extra_state_attributes
        assert attrs["days_elapsed"] == 3
        assert attrs["days_remaining"] == 27
        assert attrs["billing_cycle_progress"] == "10%"


async def test_predicted_bill_end_of_month():
    """Test predicted bill at end of month."""
    coordinator = MagicMock()
    coordinator.data = {
        "cost_projections": {
            "available": True,
            "daily_cost_estimate": 6.00,
            "fixed_charges_monthly": 15.00,
        }
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "TX"}
    
    sensor = UtilityPredictedBillSensor(coordinator, config_entry)
    
    # Test on day 28 of 30
    with patch("custom_components.utility_tariff.sensor.dt_util.now") as mock_now:
        mock_now.return_value = datetime(2024, 3, 28, 20, 0, 0)
        
        predicted = sensor.native_value
        
        # Expected: (6.00 * 28) + (6.00 * 2) + 15 = 168 + 12 + 15 = 195
        assert predicted == 195.00
        
        attrs = sensor.extra_state_attributes
        assert attrs["billing_cycle_progress"] == "93%"


async def test_predicted_bill_no_data():
    """Test predicted bill with no cost data available."""
    coordinator = MagicMock()
    coordinator.data = {
        "cost_projections": {
            "available": False
        }
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "CO"}
    
    sensor = UtilityPredictedBillSensor(coordinator, config_entry)
    
    # Should return None when no data available
    assert sensor.native_value is None
    
    # Attributes should still provide basic info
    attrs = sensor.extra_state_attributes
    assert "days_elapsed" in attrs
    assert "days_remaining" in attrs
    assert "billing_cycle_progress" in attrs


async def test_predicted_bill_attributes():
    """Test predicted bill sensor attributes."""
    coordinator = MagicMock()
    coordinator.data = {
        "cost_projections": {
            "available": True,
            "daily_cost_estimate": 5.00,
            "fixed_charges_monthly": 10.00,
            "consumption_source": "manual",
        }
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "CO"}
    
    sensor = UtilityPredictedBillSensor(coordinator, config_entry)
    
    # Check basic attributes
    assert sensor.unique_id == "test_entry_predicted_bill"
    assert sensor.icon == "mdi:currency-usd-circle-outline"
    assert sensor.native_unit_of_measurement == "$"
    assert sensor.suggested_display_precision == 2
    
    # Check state attributes
    attrs = sensor.extra_state_attributes
    assert attrs["includes_fixed_charges"] is True
    assert attrs["prediction_method"] == "daily_average"
    assert attrs["consumption_source"] == "manual"