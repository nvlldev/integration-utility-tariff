"""Test quick setup flow."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.xcel_energy_tariff.config_flow import ConfigFlow
from custom_components.xcel_energy_tariff.const import DOMAIN, SERVICE_TYPE_ELECTRIC, SERVICE_TYPE_GAS


async def test_quick_setup_electric(hass: HomeAssistant):
    """Test quick setup for electric service."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    # Single step setup with quick option
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential",
        "consumption_entity": "none",
        "average_daily_usage": 30.0,
        "setup_type": "quick"
    })
    
    # Should create entry immediately
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Xcel Energy Colorado Electric"
    assert result["data"]["state"] == "CO"
    assert result["data"]["service_type"] == SERVICE_TYPE_ELECTRIC
    assert result["data"]["rate_schedule"] == "residential"
    
    # Check all default options were set
    assert result["options"]["rate_schedule"] == "residential"
    assert result["options"]["update_frequency"] == "weekly"
    assert result["options"]["summer_months"] == "6,7,8,9"
    assert result["options"]["enable_cost_sensors"] is True
    assert result["options"]["consumption_entity"] == "none"
    assert result["options"]["average_daily_usage"] == 30.0
    assert result["options"]["include_additional_charges"] is True


async def test_quick_setup_gas(hass: HomeAssistant):
    """Test quick setup for gas service."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    result = await flow.async_step_user({
        "state": "MN",
        "service_type": SERVICE_TYPE_GAS,
        "rate_schedule": "residential_gas",
        "consumption_entity": "none",
        "average_daily_usage": 30.0,
        "setup_type": "quick"
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Xcel Energy Minnesota Gas"
    assert result["data"]["rate_schedule"] == "residential_gas"
    assert result["options"]["rate_schedule"] == "residential_gas"


async def test_quick_setup_tou(hass: HomeAssistant):
    """Test quick setup with TOU rate plan."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential_tou",
        "consumption_entity": "none",
        "average_daily_usage": 35.0,
        "setup_type": "quick"
    })
    
    # Should create entry immediately with TOU defaults
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["rate_schedule"] == "residential_tou"
    assert result["options"]["average_daily_usage"] == 35.0
    
    # Check TOU defaults were added
    assert result["options"]["peak_start"] == "15:00"
    assert result["options"]["peak_end"] == "19:00"
    assert result["options"]["shoulder_start"] == "13:00"
    assert result["options"]["shoulder_end"] == "15:00"
    assert result["options"]["custom_holidays"] == ""


async def test_custom_setup_flow(hass: HomeAssistant):
    """Test custom setup flow path."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    # Choose custom setup
    result = await flow.async_step_user({
        "state": "WI",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "rate_schedule": "residential_tou",
        "consumption_entity": "none",
        "average_daily_usage": 30.0,
        "setup_type": "custom"
    })
    
    # Should go to TOU config since TOU was selected
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "tou_config"


async def test_gas_validation_error(hass: HomeAssistant):
    """Test gas service validation for unsupported states."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock consumption entities
    hass.states.async_all = MagicMock(return_value=[])
    
    # Try gas service in Texas (not supported)
    result = await flow.async_step_user({
        "state": "TX",
        "service_type": SERVICE_TYPE_GAS,
        "rate_schedule": "residential_gas",
        "consumption_entity": "none", 
        "average_daily_usage": 30.0,
        "setup_type": "quick"
    })
    
    # Should show error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "gas_not_available"


async def test_setup_type_default(hass: HomeAssistant):
    """Test that setup_type defaults to quick."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Get the form schema
    result = await flow.async_step_user()
    
    # Check the schema has quick as default
    schema = result["data_schema"]
    setup_type_field = None
    for field in schema.schema:
        if field == "setup_type":
            setup_type_field = field
            break
    
    assert setup_type_field is not None
    assert setup_type_field.default == "quick"


async def test_complete_custom_flow_minimal(hass: HomeAssistant):
    """Test completing custom flow with minimal options."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock entity states
    hass.states.async_all = MagicMock(return_value=[])
    
    # Step 1: Choose custom setup
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC,
        "setup_type": "custom"
    })
    
    assert result["step_id"] == "rate_plan"
    
    # Step 2: Select rate plan but skip more config
    result = await flow.async_step_rate_plan({
        "rate_schedule": "residential",
        "configure_more": False
    })
    
    # Should complete immediately with defaults
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["rate_schedule"] == "residential"
    assert result["options"]["summer_months"] == "6,7,8,9"  # Default applied