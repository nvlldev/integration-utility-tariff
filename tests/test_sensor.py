"""Tests for Xcel Energy Tariff sensors."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.xcel_energy_tariff.sensor import (
    XcelCurrentRateSensor,
    XcelTOURateSensor,
    XcelTOUPeriodSensor,
    XcelFixedChargeSensor,
)


class TestSensors:
    """Test the sensor implementations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Mock data update coordinator."""
        coordinator = Mock(spec=DataUpdateCoordinator)
        coordinator.data = {
            "last_updated": "2024-01-01T12:00:00",
            "rates": {"standard": 0.11},
            "tou_rates": {
                "summer": {"peak": 0.24, "shoulder": 0.12, "off_peak": 0.08},
                "winter": {"peak": 0.20, "shoulder": 0.10, "off_peak": 0.08}
            },
            "fixed_charges": {"monthly_service": 5.47},
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
    def mock_tariff_manager(self):
        """Mock tariff manager."""
        manager = Mock()
        manager.get_current_rate.return_value = 0.12
        manager.get_current_tou_period.return_value = "Peak"
        manager._is_holiday.return_value = False
        return manager

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
        return entry

    def test_current_rate_sensor(self, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test the current rate sensor."""
        sensor = XcelCurrentRateSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry
        )
        
        # Check basic attributes
        assert sensor.name == "Xcel Energy Colorado Current Rate"
        assert sensor.unique_id == "test_entry_current_rate"
        assert sensor.native_unit_of_measurement == "$/kWh"
        
        # Check value
        assert sensor.native_value == 0.12
        
        # Check extra attributes
        attrs = sensor.extra_state_attributes
        assert attrs["rate_schedule"] == "residential_tou"
        assert "current_period" in attrs
        assert "current_season" in attrs

    def test_tou_rate_sensor(self, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test TOU rate sensors."""
        # Test peak rate sensor
        peak_sensor = XcelTOURateSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry,
            "peak",
            "Peak Rate"
        )
        
        assert peak_sensor.name == "Xcel Energy Colorado Peak Rate"
        assert peak_sensor.unique_id == "test_entry_tou_peak"
        
        # Mock current month for summer
        with patch('custom_components.xcel_energy_tariff.sensor.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 7, 1)  # July
            assert peak_sensor.native_value == 0.24  # Summer peak rate
        
        # Test off-peak sensor
        off_peak_sensor = XcelTOURateSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry,
            "off_peak",
            "Off-Peak Rate"
        )
        
        with patch('custom_components.xcel_energy_tariff.sensor.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 1)  # December
            assert off_peak_sensor.native_value == 0.08  # Winter off-peak rate

    def test_tou_period_sensor(self, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test TOU period sensor."""
        sensor = XcelTOUPeriodSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry
        )
        
        assert sensor.name == "Xcel Energy Colorado Current TOU Period"
        assert sensor.unique_id == "test_entry_tou_period"
        assert sensor.native_value == "Peak"
        
        # Check attributes
        attrs = sensor.extra_state_attributes
        assert "current_season" in attrs
        assert "is_weekday" in attrs
        assert "is_holiday" in attrs
        assert "current_hour" in attrs
        assert "peak_hours" in attrs
        assert "shoulder_hours" in attrs
        assert "off_peak_hours" in attrs

    def test_fixed_charge_sensor(self, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test fixed charge sensor."""
        sensor = XcelFixedChargeSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry
        )
        
        assert sensor.name == "Xcel Energy Colorado Monthly Service Charge"
        assert sensor.unique_id == "test_entry_fixed_charge"
        assert sensor.native_unit_of_measurement == "$"
        assert sensor.native_value == 5.47

    def test_sensor_with_gas_service(self, mock_coordinator, mock_tariff_manager):
        """Test sensors with gas service type."""
        config_entry = Mock()
        config_entry.entry_id = "gas_entry"
        config_entry.data = {
            "state": "CO",
            "service_type": "gas",
            "rate_schedule": "residential"
        }
        
        sensor = XcelCurrentRateSensor(
            mock_coordinator,
            mock_tariff_manager,
            config_entry
        )
        
        # Gas should use $/therm instead of $/kWh
        assert sensor.native_unit_of_measurement == "$/therm"

    @patch('custom_components.xcel_energy_tariff.sensor.datetime')
    def test_current_period_attribute(self, mock_datetime, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test that current period is correctly set in attributes."""
        sensor = XcelCurrentRateSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry
        )
        
        # Mock a specific time
        mock_datetime.now.return_value = datetime(2024, 7, 2, 16, 0)  # Tuesday 4 PM in July
        mock_tariff_manager.get_current_tou_period.return_value = "Shoulder"
        
        attrs = sensor.extra_state_attributes
        assert attrs["current_period"] == "shoulder"
        assert attrs["current_season"] == "summer"
        assert attrs["is_holiday"] is False

    def test_tou_period_sensor_holiday_attribute(self, mock_coordinator, mock_tariff_manager, mock_config_entry):
        """Test TOU period sensor shows holiday status."""
        sensor = XcelTOUPeriodSensor(
            mock_coordinator,
            mock_tariff_manager,
            mock_config_entry
        )
        
        # Test with holiday
        mock_tariff_manager._is_holiday.return_value = True
        attrs = sensor.extra_state_attributes
        assert attrs["is_holiday"] is True
        
        # Test observed holidays list
        assert "observed_holidays" in attrs
        assert isinstance(attrs["observed_holidays"], list)
        assert "New Year's Day" in attrs["observed_holidays"]