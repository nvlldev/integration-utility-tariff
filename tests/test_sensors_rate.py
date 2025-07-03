"""Test rate sensors."""
import pytest
from unittest.mock import Mock

from custom_components.utility_tariff.sensors.rate import (
    UtilityCurrentRateSensor,
    UtilityCurrentRateWithFeesSensor,
    UtilityPeakRateSensor,
    UtilityShoulderRateSensor,
    UtilityOffPeakRateSensor,
)
from custom_components.utility_tariff.const import DOMAIN


class TestRateSensors:
    """Test rate sensor implementations."""
    
    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with rate data."""
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
            "current_rate": 0.12,
            "current_period": "Peak",
            "current_season": "summer",
            "is_holiday": False,
            "is_weekend": False,
            "all_current_rates": {
                "tou_rates": {
                    "peak": 0.24,
                    "shoulder": 0.15,
                    "off_peak": 0.08
                },
                "total_additional": 0.025
            }
        }
        return coordinator
    
    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"state": "CO"}
        entry.options = {"rate_schedule": "residential_tou"}
        return entry
    
    def test_current_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test current rate sensor."""
        sensor = UtilityCurrentRateSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Current Rate"
        assert sensor._attr_unique_id == "test_entry_current_rate"
        assert sensor._attr_native_unit_of_measurement == "$/kWh"
        assert sensor._attr_suggested_display_precision == 4
        assert sensor._attr_icon == "mdi:currency-usd"
        
        assert sensor.native_value == 0.12
        
        attrs = sensor.extra_state_attributes
        assert attrs["period"] == "Peak"
        assert attrs["season"] == "summer"
        assert attrs["is_holiday"] is False
        assert attrs["is_weekend"] is False
    
    def test_current_rate_with_fees_sensor(self, mock_coordinator, mock_config_entry):
        """Test current rate with fees sensor."""
        sensor = UtilityCurrentRateWithFeesSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Current Rate With Fees"
        assert sensor.native_value == 0.145  # 0.12 + 0.025
        
    def test_current_rate_with_fees_no_base_rate(self, mock_coordinator, mock_config_entry):
        """Test current rate with fees when base rate is None."""
        mock_coordinator.data["current_rate"] = None
        sensor = UtilityCurrentRateWithFeesSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value is None
    
    def test_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test peak rate sensor."""
        sensor = UtilityPeakRateSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Peak Rate"
        assert sensor._attr_unique_id == "test_entry_peak_rate"
        assert sensor._attr_icon == "mdi:trending-up"
        assert sensor.native_value == 0.24
    
    def test_shoulder_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test shoulder rate sensor."""
        sensor = UtilityShoulderRateSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Shoulder Rate"
        assert sensor._attr_unique_id == "test_entry_shoulder_rate"
        assert sensor._attr_icon == "mdi:trending-neutral"
        assert sensor.native_value == 0.15
    
    def test_off_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test off-peak rate sensor."""
        sensor = UtilityOffPeakRateSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Off-Peak Rate"
        assert sensor._attr_unique_id == "test_entry_off_peak_rate"
        assert sensor._attr_icon == "mdi:trending-down"
        assert sensor.native_value == 0.08
    
    def test_rate_sensors_with_missing_data(self, mock_coordinator, mock_config_entry):
        """Test rate sensors when TOU rates are missing."""
        mock_coordinator.data["all_current_rates"] = {}
        
        peak = UtilityPeakRateSensor(mock_coordinator, mock_config_entry)
        shoulder = UtilityShoulderRateSensor(mock_coordinator, mock_config_entry)
        off_peak = UtilityOffPeakRateSensor(mock_coordinator, mock_config_entry)
        
        assert peak.native_value is None
        assert shoulder.native_value is None
        assert off_peak.native_value is None