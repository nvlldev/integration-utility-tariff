"""Test energy tracking sensors."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import Event

from custom_components.utility_tariff.sensors.energy import (
    UtilityEnergyDeliveredTotalSensor,
    UtilityEnergyReceivedTotalSensor,
)
from custom_components.utility_tariff.const import DOMAIN


class TestEnergySensors:
    """Test energy sensor implementations."""
    
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
        coordinator.data = {}
        return coordinator
    
    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"state": "CO"}
        entry.options = {
            "consumption_entity": "sensor.home_energy",
            "return_entity": "sensor.solar_export"
        }
        return entry
    
    @pytest.mark.asyncio
    async def test_energy_delivered_sensor_init(self, mock_coordinator, mock_config_entry):
        """Test energy delivered sensor initialization."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        
        assert sensor._attr_name == "Energy Delivered"
        assert sensor._attr_unique_id == "test_entry_energy_delivered"
        assert sensor._attr_device_class.value == "energy"
        assert sensor._attr_state_class.value == "total_increasing"
        assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert sensor._attr_icon == "mdi:transmission-tower-import"
        assert sensor._cumulative_received == 0.0
        assert sensor._last_value is None
    
    @pytest.mark.asyncio
    async def test_energy_delivered_restore_state(self, mock_coordinator, mock_config_entry):
        """Test restoring state from previous session."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        
        # Mock previous state
        mock_last_state = Mock()
        mock_last_state.state = "150.5"
        mock_last_state.attributes = {"last_value": 145.2}
        
        with patch.object(sensor, 'async_get_last_state', return_value=mock_last_state):
            await sensor.async_added_to_hass()
            
        assert sensor._cumulative_received == 150.5
        assert sensor._last_value == 145.2
    
    @pytest.mark.asyncio
    async def test_energy_delivered_invalid_restore(self, mock_coordinator, mock_config_entry):
        """Test handling invalid restored state."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        
        # Mock invalid state
        mock_last_state = Mock()
        mock_last_state.state = "invalid"
        mock_last_state.attributes = {}
        
        with patch.object(sensor, 'async_get_last_state', return_value=mock_last_state):
            await sensor.async_added_to_hass()
            
        assert sensor._cumulative_received == 0.0
        assert sensor._last_value is None
    
    def test_energy_delivered_state_change(self, mock_coordinator, mock_config_entry):
        """Test handling state changes."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        sensor._last_value = 100.0
        sensor._cumulative_received = 100.0
        
        # Mock state change event
        event = Mock(spec=Event)
        new_state = Mock()
        new_state.state = "105.5"
        new_state.attributes = {"unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR}
        event.data = {"new_state": new_state}
        
        # Mock the async_write_ha_state method to avoid entity registration issues
        with patch.object(sensor, 'async_write_ha_state'):
            sensor._handle_source_state_change(event)
        
        assert sensor._last_value == 105.5
        assert sensor._cumulative_received == 105.5  # 100 + 5.5
    
    def test_energy_delivered_meter_reset(self, mock_coordinator, mock_config_entry):
        """Test handling meter reset."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        sensor._last_value = 1000.0
        sensor._cumulative_received = 1000.0
        
        # Mock meter reset (new value less than last)
        event = Mock(spec=Event)
        new_state = Mock()
        new_state.state = "5.0"
        new_state.attributes = {"unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR}
        event.data = {"new_state": new_state}
        
        # Mock the async_write_ha_state method to avoid entity registration issues
        with patch.object(sensor, 'async_write_ha_state'):
            sensor._handle_source_state_change(event)
        
        assert sensor._last_value == 5.0
        assert sensor._cumulative_received == 1005.0  # 1000 + 5
    
    def test_energy_delivered_wh_conversion(self, mock_coordinator, mock_config_entry):
        """Test Wh to kWh conversion."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        sensor._last_value = 0.0
        sensor._cumulative_received = 0.0
        
        # Mock state in Wh
        event = Mock(spec=Event)
        new_state = Mock()
        new_state.state = "5000"  # 5000 Wh = 5 kWh
        new_state.attributes = {"unit_of_measurement": UnitOfEnergy.WATT_HOUR}
        event.data = {"new_state": new_state}
        
        # Mock the async_write_ha_state method to avoid entity registration issues
        with patch.object(sensor, 'async_write_ha_state'):
            sensor._handle_source_state_change(event)
        
        assert sensor._last_value == 5.0
        assert sensor._cumulative_received == 5.0
    
    def test_energy_delivered_unavailable_state(self, mock_coordinator, mock_config_entry):
        """Test handling unavailable state."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        original_value = 100.0
        sensor._cumulative_received = original_value
        
        # Mock unavailable state
        event = Mock(spec=Event)
        new_state = Mock()
        new_state.state = STATE_UNAVAILABLE
        event.data = {"new_state": new_state}
        
        sensor._handle_source_state_change(event)
        
        # Value should not change
        assert sensor._cumulative_received == original_value
    
    def test_energy_delivered_attributes(self, mock_coordinator, mock_config_entry):
        """Test sensor attributes."""
        sensor = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        sensor._cumulative_received = 150.5
        sensor._last_value = 145.2
        
        # Mock current entity state
        mock_state = Mock()
        mock_state.state = "145.2"
        mock_state.attributes = {"unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR}
        sensor.hass = Mock()
        sensor.hass.states.get.return_value = mock_state
        
        attrs = sensor.extra_state_attributes
        assert attrs["meter_type"] == "energy_delivered_total"
        assert attrs["source_entity"] == "sensor.home_energy"
        assert attrs["last_value"] == 145.2
        assert attrs["cumulative_delivered"] == 150.5
        assert attrs["current_reading"] == 145.2
    
    @pytest.mark.asyncio
    async def test_energy_received_sensor(self, mock_coordinator, mock_config_entry):
        """Test energy received sensor (similar structure to delivered)."""
        sensor = UtilityEnergyReceivedTotalSensor(mock_coordinator, mock_config_entry)
        sensor.hass = mock_coordinator.hass  # Ensure hass is set
        
        assert sensor._attr_name == "Energy Received"
        assert sensor._attr_unique_id == "test_entry_energy_received"
        assert sensor._attr_icon == "mdi:transmission-tower-export"
        
        # Test that it tracks return entity instead of consumption
        attrs = sensor.extra_state_attributes
        assert attrs["source_entity"] == "sensor.solar_export"
    
    def test_energy_sensors_no_entity_configured(self, mock_coordinator, mock_config_entry):
        """Test sensors when no entity is configured."""
        mock_config_entry.options = {
            "consumption_entity": "none",
            "return_entity": "none"
        }
        
        delivered = UtilityEnergyDeliveredTotalSensor(mock_coordinator, mock_config_entry)
        received = UtilityEnergyReceivedTotalSensor(mock_coordinator, mock_config_entry)
        
        assert delivered.extra_state_attributes["source_entity"] is None
        assert received.extra_state_attributes["source_entity"] is None