"""Test the base sensor class."""
import pytest
from unittest.mock import Mock

from custom_components.utility_tariff.sensors.base import UtilitySensorBase
from custom_components.utility_tariff.const import DOMAIN, ALL_STATES


class TestUtilitySensorBase:
    """Test the UtilitySensorBase class."""
    
    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = Mock()
        coordinator.hass = Mock()
        mock_provider = Mock()
        mock_provider.name = "Test Provider"
        coordinator.hass.data = {
            DOMAIN: {
                "test_entry": {
                    "provider": mock_provider
                }
            }
        }
        return coordinator
    
    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"state": "CO"}
        entry.options = {"rate_schedule": "residential"}
        return entry
    
    def test_base_sensor_initialization(self, mock_coordinator, mock_config_entry):
        """Test base sensor initialization."""
        sensor = UtilitySensorBase(
            mock_coordinator,
            mock_config_entry,
            "test_key",
            "Test Sensor"
        )
        
        assert sensor._config_entry == mock_config_entry
        assert sensor._key == "test_key"
        assert sensor._attr_name == "Test Sensor"
        assert sensor._attr_unique_id == "test_entry_test_key"
        assert sensor._attr_has_entity_name is True
        
    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info generation."""
        sensor = UtilitySensorBase(
            mock_coordinator,
            mock_config_entry,
            "test_key",
            "Test Sensor"
        )
        
        device_info = sensor._attr_device_info
        assert device_info["identifiers"] == {(DOMAIN, "test_entry")}
        assert device_info["name"] == "Test Provider Colorado"
        assert device_info["manufacturer"] == "Test Provider"
        assert device_info["model"] == "residential"
    
    def test_state_name_lookup(self, mock_coordinator, mock_config_entry):
        """Test state name lookup from ALL_STATES."""
        # Test with known state
        sensor = UtilitySensorBase(
            mock_coordinator,
            mock_config_entry,
            "test_key",
            "Test Sensor"
        )
        
        assert "Colorado" in sensor._attr_device_info["name"]
        
        # Test with unknown state
        mock_config_entry.data = {"state": "XX"}
        sensor2 = UtilitySensorBase(
            mock_coordinator,
            mock_config_entry,
            "test_key2",
            "Test Sensor 2"
        )
        
        # Should fall back to state code
        assert "XX" in sensor2._attr_device_info["name"]