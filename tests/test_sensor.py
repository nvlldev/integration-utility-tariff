"""Tests for Utility Tariff sensors."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from custom_components.utility_tariff.const import DOMAIN

from custom_components.utility_tariff.sensors import (
    UtilityCurrentRateSensor,
    UtilityPeakRateSensor,
    UtilityShoulderRateSensor,
    UtilityOffPeakRateSensor,
    UtilityTOUPeriodSensor,
    UtilityFixedChargeSensor,
)


class TestSensors:
    """Test the sensor implementations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Mock data update coordinator."""
        coordinator = Mock(spec=DataUpdateCoordinator)
        
        # Mock hass instance with necessary data
        coordinator.hass = Mock()
        coordinator.hass.data = {
            DOMAIN: {
                "test_entry": {
                    "provider": Mock(name="Test Provider")
                }
            }
        }
        
        coordinator.data = {
            "last_updated": "2024-01-01T12:00:00",
            "current_rate": 0.12,
            "current_period": "Peak",
            "current_season": "summer",
            "is_holiday": False,
            "is_weekend": False,
            "rates": {"standard": 0.11},
            "all_current_rates": {
                "tou_rates": {
                    "peak": 0.24,
                    "shoulder": 0.15,
                    "off_peak": 0.08
                },
                "total_additional": 0.025,
                "fixed_charges": {"monthly_service": 5.47}
            },
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                },
                "winter": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                }
            }
        }
        return coordinator

    @pytest.fixture
    def mock_config_entry(self):
        """Mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "state": "CO",
            "service_type": "electric",
            "rate_schedule": "residential_tou"
        }
        entry.options = {"rate_schedule": "residential_tou"}
        return entry

    def test_current_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test the current rate sensor."""
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        # Check basic attributes
        assert sensor._attr_name == "Current Rate"
        assert sensor._attr_unique_id == "test_entry_current_rate"
        assert sensor._attr_native_unit_of_measurement == "$/kWh"
        
        # Check value
        assert sensor.native_value == 0.12
        
        # Check extra attributes
        attrs = sensor.extra_state_attributes
        assert attrs["period"] == "Peak"
        assert attrs["season"] == "summer"
        assert attrs["is_holiday"] is False
        assert attrs["is_weekend"] is False

    def test_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test peak rate sensor."""
        sensor = UtilityPeakRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Peak Rate"
        assert sensor._attr_unique_id == "test_entry_peak_rate"
        assert sensor.native_value == 0.24

    def test_shoulder_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test shoulder rate sensor."""
        sensor = UtilityShoulderRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Shoulder Rate"
        assert sensor._attr_unique_id == "test_entry_shoulder_rate"
        assert sensor.native_value == 0.15

    def test_off_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test off-peak rate sensor."""
        sensor = UtilityOffPeakRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Off-Peak Rate"
        assert sensor._attr_unique_id == "test_entry_off_peak_rate"
        assert sensor.native_value == 0.08

    def test_tou_period_sensor(self, mock_coordinator, mock_config_entry):
        """Test TOU period sensor."""
        sensor = UtilityTOUPeriodSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "TOU Period"
        assert sensor._attr_unique_id == "test_entry_tou_period"
        assert sensor.native_value == "Peak"
        
        # Check attributes
        attrs = sensor.extra_state_attributes
        assert attrs["peak_rate"] == 0.24
        assert attrs["shoulder_rate"] == 0.15
        assert attrs["off_peak_rate"] == 0.08
        assert "schedule" in attrs

    def test_fixed_charge_sensor(self, mock_coordinator, mock_config_entry):
        """Test fixed charge sensor."""
        sensor = UtilityFixedChargeSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Monthly Service Charge"
        assert sensor._attr_unique_id == "test_entry_fixed_charge"
        assert sensor._attr_native_unit_of_measurement == "$"
        assert sensor.native_value == 5.47

    def test_sensor_with_gas_service(self, mock_coordinator):
        """Test sensors with gas service type."""
        # Set up gas entry in hass data
        mock_coordinator.hass.data[DOMAIN]["gas_entry"] = {
            "provider": Mock(name="Test Provider")
        }
        
        config_entry = Mock()
        config_entry.entry_id = "gas_entry"
        config_entry.data = {
            "state": "CO",
            "service_type": "gas",
            "rate_schedule": "residential"
        }
        config_entry.options = {"rate_schedule": "residential"}
        
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            config_entry
        )
        
        # Gas should use $/therm instead of $/kWh
        assert sensor._attr_native_unit_of_measurement == "$/therm"

    def test_current_rate_sensor_missing_data(self, mock_coordinator, mock_config_entry):
        """Test current rate sensor with missing data."""
        mock_coordinator.data = {}
        
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        # Should return None when data is missing
        assert sensor.native_value is None

    def test_tou_rates_missing(self, mock_coordinator, mock_config_entry):
        """Test TOU rate sensors when rates are missing."""
        mock_coordinator.data["all_current_rates"] = {}
        
        peak_sensor = UtilityPeakRateSensor(mock_coordinator, mock_config_entry)
        shoulder_sensor = UtilityShoulderRateSensor(mock_coordinator, mock_config_entry)
        off_peak_sensor = UtilityOffPeakRateSensor(mock_coordinator, mock_config_entry)
        
        assert peak_sensor.native_value is None
        assert shoulder_sensor.native_value is None
        assert off_peak_sensor.native_value is None

    def test_fixed_charges_missing(self, mock_coordinator, mock_config_entry):
        """Test fixed charge sensor when charges are missing."""
        mock_coordinator.data["all_current_rates"] = {}
        
        sensor = UtilityFixedChargeSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor.native_value is None