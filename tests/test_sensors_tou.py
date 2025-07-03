"""Test Time-of-Use sensors."""
import pytest
from unittest.mock import Mock

from custom_components.utility_tariff.sensors.tou import (
    UtilityTOUPeriodSensor,
    UtilityTimeUntilNextPeriodSensor,
)
from custom_components.utility_tariff.const import DOMAIN


class TestTOUSensors:
    """Test TOU sensor implementations."""
    
    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with TOU data."""
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
            "current_period": "Peak",
            "all_current_rates": {
                "tou_rates": {
                    "peak": 0.24,
                    "shoulder": 0.15,
                    "off_peak": 0.08
                }
            },
            "tou_schedule": {
                "peak": {"start": 15, "end": 19},
                "shoulder": {"start": 13, "end": 15}
            },
            "next_period_change": {
                "available": True,
                "minutes_until": 45,
                "next_period": "Off-Peak",
                "next_change": "2024-01-15T19:00:00"
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
    
    def test_tou_period_sensor(self, mock_coordinator, mock_config_entry):
        """Test TOU period sensor."""
        sensor = UtilityTOUPeriodSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "TOU Period"
        assert sensor._attr_unique_id == "test_entry_tou_period"
        assert sensor._attr_icon == "mdi:clock-outline"
        
        assert sensor.native_value == "Peak"
        
        attrs = sensor.extra_state_attributes
        assert attrs["peak_rate"] == 0.24
        assert attrs["shoulder_rate"] == 0.15
        assert attrs["off_peak_rate"] == 0.08
        assert attrs["schedule"] == mock_coordinator.data["tou_schedule"]
    
    def test_tou_period_sensor_unknown(self, mock_coordinator, mock_config_entry):
        """Test TOU period sensor with no period."""
        mock_coordinator.data["current_period"] = None
        sensor = UtilityTOUPeriodSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value == "Unknown"
    
    def test_time_until_next_period_sensor(self, mock_coordinator, mock_config_entry):
        """Test time until next period sensor."""
        sensor = UtilityTimeUntilNextPeriodSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Time Until Next Period"
        assert sensor._attr_unique_id == "test_entry_time_until_next_period"
        assert sensor._attr_native_unit_of_measurement == "min"
        assert sensor._attr_icon == "mdi:timer-sand"
        
        assert sensor.native_value == 45
        
        attrs = sensor.extra_state_attributes
        assert attrs["next_period"] == "Off-Peak"
        assert attrs["next_change_time"] == "2024-01-15T19:00:00"
    
    def test_time_until_next_period_not_available(self, mock_coordinator, mock_config_entry):
        """Test time until next period when not available."""
        mock_coordinator.data["next_period_change"] = {"available": False}
        sensor = UtilityTimeUntilNextPeriodSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}
    
    def test_time_until_next_period_missing_data(self, mock_coordinator, mock_config_entry):
        """Test time until next period with missing data."""
        mock_coordinator.data["next_period_change"] = {}
        sensor = UtilityTimeUntilNextPeriodSensor(mock_coordinator, mock_config_entry)
        
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}