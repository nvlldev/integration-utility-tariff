"""Test consumption entity feature."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.xcel_energy_tariff.config_flow import ConfigFlow
from custom_components.xcel_energy_tariff.coordinator import XcelDynamicCoordinator


async def test_config_flow_finds_energy_sensors(hass: HomeAssistant):
    """Test that config flow properly finds energy sensors."""
    # Mock states
    mock_states = [
        MagicMock(
            entity_id="sensor.home_energy_daily",
            attributes={"unit_of_measurement": "kWh", "friendly_name": "Home Energy Daily"}
        ),
        MagicMock(
            entity_id="sensor.solar_energy_monthly", 
            attributes={"unit_of_measurement": "kWh", "friendly_name": "Solar Energy Monthly"}
        ),
        MagicMock(
            entity_id="sensor.power_meter",
            attributes={"unit_of_measurement": "W", "friendly_name": "Power Meter"}  # Wrong unit
        ),
        MagicMock(
            entity_id="sensor.energy_total",
            attributes={"unit_of_measurement": "Wh", "friendly_name": "Energy Total"}
        ),
    ]
    
    hass.states.async_all = MagicMock(return_value=mock_states)
    
    # Mock entity registry
    mock_registry = MagicMock()
    mock_registry.entities = {}
    
    with patch("custom_components.xcel_energy_tariff.config_flow.er.async_get", return_value=mock_registry):
        flow = ConfigFlow()
        flow.hass = hass
        flow._data = {"title": "Test", "state": "CO", "service_type": "electric"}
        flow._options = {}
        
        result = await flow.async_step_additional_options()
        
        # Check that the right entities were found
        schema = result["data_schema"]
        consumption_field = None
        for field in schema.schema:
            if field == "consumption_entity":
                consumption_field = field
                break
                
        assert consumption_field is not None
        entity_options = dict(schema.schema[consumption_field].config["choices"])
        
        # Should have found the kWh and Wh sensors, plus "none" option
        assert "none" in entity_options
        assert "sensor.home_energy_daily" in entity_options
        assert "sensor.solar_energy_monthly" in entity_options
        assert "sensor.energy_total" in entity_options
        assert "sensor.power_meter" not in entity_options  # Wrong unit


async def test_coordinator_uses_consumption_entity(hass: HomeAssistant):
    """Test that coordinator properly uses consumption entity."""
    # Mock tariff manager
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.home_energy_daily",
        "average_daily_usage": 30.0
    }
    
    # Mock PDF coordinator
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    # Create dynamic coordinator
    coordinator = XcelDynamicCoordinator(hass, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock state for consumption entity
    mock_state = MagicMock()
    mock_state.state = "25.5"
    mock_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Home Energy Daily",
        "state_class": "total_increasing"
    }
    hass.states.get = MagicMock(return_value=mock_state)
    
    # Test cost calculation
    costs = coordinator._calculate_costs(0.10, {"fixed_charges": {"monthly_service": 10}})
    
    assert costs["available"] is True
    assert costs["daily_kwh_used"] == 25.5
    assert costs["consumption_source"] == "entity_daily"
    assert costs["consumption_entity"] == "sensor.home_energy_daily"
    assert costs["daily_cost_estimate"] == 2.55  # 25.5 kWh * $0.10
    

async def test_consumption_source_detection(hass: HomeAssistant):
    """Test detection of consumption source type."""
    # Mock tariff manager
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.energy_monthly",
        "average_daily_usage": 30.0
    }
    
    # Mock PDF coordinator
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    # Create dynamic coordinator
    coordinator = XcelDynamicCoordinator(hass, mock_tariff_manager, mock_pdf_coordinator)
    
    # Test monthly sensor
    mock_state = MagicMock()
    mock_state.state = "900"  # 900 kWh for the month
    mock_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Energy Monthly Total"
    }
    hass.states.get = MagicMock(return_value=mock_state)
    
    costs = coordinator._calculate_costs(0.10, {})
    
    assert costs["consumption_source"] == "entity_monthly"
    assert costs["daily_kwh_used"] == 30.0  # 900 / 30 days
    
    # Test yearly sensor
    mock_state.attributes["friendly_name"] = "Annual Energy Consumption"
    costs = coordinator._calculate_costs(0.10, {})
    
    assert costs["consumption_source"] == "entity_yearly"
    assert costs["daily_kwh_used"] == pytest.approx(2.47, 0.01)  # 900 / 365 days


async def test_fallback_to_manual_on_error(hass: HomeAssistant):
    """Test fallback to manual entry when entity unavailable."""
    # Mock tariff manager
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.missing_entity",
        "average_daily_usage": 35.0
    }
    
    # Mock PDF coordinator
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    # Create dynamic coordinator
    coordinator = XcelDynamicCoordinator(hass, mock_tariff_manager, mock_pdf_coordinator)
    
    # No state found
    hass.states.get = MagicMock(return_value=None)
    
    costs = coordinator._calculate_costs(0.10, {})
    
    assert costs["consumption_source"] == "manual"
    assert costs["daily_kwh_used"] == 35.0
    assert "consumption_entity" not in costs  # Don't include if using manual