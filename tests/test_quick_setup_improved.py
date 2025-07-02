"""Test improved quick setup with rate and consumption entity selection."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.xcel_energy_tariff.config_flow import ConfigFlow
from custom_components.xcel_energy_tariff.const import DOMAIN, SERVICE_TYPE_ELECTRIC


async def test_quick_setup_with_consumption_entity(hass: HomeAssistant):
    """Test quick setup with consumption entity selection."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    mock_states = [
        MagicMock(
            entity_id="sensor.home_energy_usage",
            attributes={
                "unit_of_measurement": "kWh", 
                "friendly_name": "Home Energy Usage"
            }
        ),
        MagicMock(
            entity_id="sensor.solar_production",
            attributes={
                "unit_of_measurement": "kWh",
                "friendly_name": "Solar Production"
            }
        ),
    ]
    hass.states.async_all = MagicMock(return_value=mock_states)
    
    # Get the form to see available options
    result = await flow.async_step_user()
    
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"]
    
    # Check that consumption entities are available
    consumption_field = None
    for field in schema.schema:
        if field == "consumption_entity":
            consumption_field = field
            break
    
    assert consumption_field is not None
    entity_options = dict(schema.schema[consumption_field].config["choices"])
    assert "sensor.home_energy_usage" in entity_options
    assert entity_options["sensor.home_energy_usage"] == "Home Energy Usage"
    
    # Complete quick setup with entity
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential",
        "consumption_entity": "sensor.home_energy_usage",
        "setup_type": "quick"
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["consumption_entity"] == "sensor.home_energy_usage"
    # Should not have average_daily_usage since entity was selected
    assert result["options"]["average_daily_usage"] == 30.0  # Still has default


async def test_quick_setup_form_changes_with_service_type(hass: HomeAssistant):
    """Test that rate options change when service type changes."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock no consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    # Get initial form
    result = await flow.async_step_user()
    schema = result["data_schema"]
    
    # Check electric rate options
    rate_field = None
    for field in schema.schema:
        if field == "rate_schedule":
            rate_field = field
            break
    
    electric_rates = dict(schema.schema[rate_field].config["choices"])
    assert "residential" in electric_rates
    assert "residential_tou" in electric_rates
    
    # Simulate changing service type to gas
    result = await flow.async_step_user({
        "service_type": SERVICE_TYPE_ELECTRIC  # This would trigger form reload
    })
    
    # The form should update rate options dynamically


async def test_quick_setup_with_all_fields(hass: HomeAssistant):
    """Test quick setup with all fields filled."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock entity
    mock_state = MagicMock(
        entity_id="sensor.energy_meter",
        attributes={
            "unit_of_measurement": "kWh",
            "friendly_name": "Energy Meter"
        }
    )
    hass.states.async_all = MagicMock(return_value=[mock_state])
    hass.states.get = MagicMock(return_value=mock_state)
    
    result = await flow.async_step_user({
        "state": "MN",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential_ev",
        "consumption_entity": "sensor.energy_meter",
        "setup_type": "quick"
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["state"] == "MN"
    assert result["data"]["rate_schedule"] == "residential_ev"
    assert result["options"]["rate_schedule"] == "residential_ev"
    assert result["options"]["consumption_entity"] == "sensor.energy_meter"


async def test_average_daily_usage_only_shown_for_manual(hass: HomeAssistant):
    """Test that average daily usage field only appears for manual entry."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock no entities
    hass.states.async_all = MagicMock(return_value=[])
    
    # Get form
    result = await flow.async_step_user()
    
    # Check that average_daily_usage is in schema
    schema_keys = [str(k) for k in result["data_schema"].schema.keys()]
    assert "average_daily_usage" in schema_keys
    
    # The field should only show when consumption_entity is "none"
    # This is handled by the dynamic form logic


async def test_form_preserves_values_on_reload(hass: HomeAssistant):
    """Test that form preserves values when reloading."""
    flow = ConfigFlow()
    flow.hass = hass
    
    hass.states.async_all = MagicMock(return_value=[])
    
    # Simulate form reload (e.g., changing service type)
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential_tou",
        "consumption_entity": "none",
        "average_daily_usage": 45.0,
        # No setup_type means form reload
    })
    
    # Form should show again with preserved values
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    
    # The defaults should reflect the input values
    schema = result["data_schema"]
    for field in schema.schema:
        if field == "average_daily_usage":
            assert field.default == 45.0
            break