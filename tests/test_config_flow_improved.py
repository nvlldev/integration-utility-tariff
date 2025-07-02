"""Test improved config flow."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.xcel_energy_tariff.config_flow import ConfigFlow
from custom_components.xcel_energy_tariff.const import DOMAIN, SERVICE_TYPE_ELECTRIC


async def test_simple_setup_flow(hass: HomeAssistant):
    """Test the simplified setup flow using all defaults."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Step 1: Initial setup
    result = await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_advanced"
    assert "Residential" in result["description_placeholders"]["default_rate"]
    
    # Step 2: Skip advanced configuration
    result = await flow.async_step_configure_advanced({
        "configure_advanced": False
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Xcel Energy Colorado Electric"
    assert result["data"]["state"] == "CO"
    assert result["data"]["service_type"] == SERVICE_TYPE_ELECTRIC
    assert result["options"]["rate_schedule"] == "residential"
    assert result["options"]["update_frequency"] == "weekly"
    assert result["options"]["enable_cost_sensors"] is True


async def test_advanced_setup_flow(hass: HomeAssistant):
    """Test the advanced setup flow."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Mock entity states
    hass.states.async_all = MagicMock(return_value=[])
    
    # Step 1: Initial setup
    result = await flow.async_step_user({
        "state": "MN",
        "service_type": SERVICE_TYPE_ELECTRIC
    })
    
    # Step 2: Choose advanced configuration
    result = await flow.async_step_configure_advanced({
        "configure_advanced": True
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rate_plan"
    
    # Step 3: Select TOU rate and continue
    result = await flow.async_step_rate_plan({
        "rate_schedule": "residential_tou",
        "update_frequency": "daily",
        "configure_more": True
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "tou_config"
    
    # Step 4: Configure TOU settings
    result = await flow.async_step_tou_config({
        "peak_start": "14:00",
        "peak_end": "20:00",
        "skip_additional": False
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "additional_options"
    
    # Step 5: Configure additional options
    result = await flow.async_step_additional_options({
        "summer_months": "5,6,7,8,9",
        "enable_cost_sensors": True,
        "consumption_entity": "none",
        "average_daily_usage": 25.0,
        "include_additional_charges": True
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["rate_schedule"] == "residential_tou"
    assert result["options"]["update_frequency"] == "daily"
    assert result["options"]["peak_start"] == "14:00"
    assert result["options"]["average_daily_usage"] == 25.0


async def test_quick_tou_setup(hass: HomeAssistant):
    """Test quick setup with TOU but skip additional options."""
    flow = ConfigFlow()
    flow.hass = hass
    
    # Initial setup
    await flow.async_step_user({
        "state": "CO",
        "service_type": SERVICE_TYPE_ELECTRIC
    })
    
    # Choose advanced
    await flow.async_step_configure_advanced({
        "configure_advanced": True
    })
    
    # Select TOU but skip more config
    result = await flow.async_step_rate_plan({
        "rate_schedule": "residential_tou",
        "configure_more": False
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["rate_schedule"] == "residential_tou"
    # Should have default TOU settings
    assert "peak_start" not in result["options"]  # Uses defaults


async def test_simplified_options_flow(hass: HomeAssistant):
    """Test the simplified options flow."""
    from custom_components.xcel_energy_tariff.config_flow import OptionsFlow
    
    # Mock config entry
    config_entry = MagicMock()
    config_entry.data = {"state": "CO", "service_type": SERVICE_TYPE_ELECTRIC}
    config_entry.options = {
        "rate_schedule": "residential",
        "update_frequency": "weekly",
        "average_daily_usage": 30.0
    }
    
    # Mock states
    hass.states.async_all = MagicMock(return_value=[])
    
    flow = OptionsFlow(config_entry)
    flow.hass = hass
    
    # Test simple update without advanced
    result = await flow.async_step_init({
        "rate_schedule": "residential_tou",
        "consumption_entity": "none",
        "average_daily_usage": 35.0,
        "enable_cost_sensors": True,
        "show_advanced": False
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["rate_schedule"] == "residential_tou"
    assert result["data"]["average_daily_usage"] == 35.0
    assert result["data"]["update_frequency"] == "weekly"  # Preserved


async def test_advanced_options_flow(hass: HomeAssistant):
    """Test the advanced options flow."""
    from custom_components.xcel_energy_tariff.config_flow import OptionsFlow
    
    # Mock config entry
    config_entry = MagicMock()
    config_entry.data = {"state": "CO", "service_type": SERVICE_TYPE_ELECTRIC}
    config_entry.options = {"rate_schedule": "residential_tou"}
    
    flow = OptionsFlow(config_entry)
    flow.hass = hass
    
    # Choose to show advanced
    result = await flow.async_step_init({
        "show_advanced": True
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "advanced"
    
    # Configure advanced options
    result = await flow.async_step_advanced({
        "update_frequency": "daily",
        "summer_months": "4,5,6,7,8,9",
        "peak_start": "16:00",
        "peak_end": "21:00"
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["update_frequency"] == "daily"
    assert result["data"]["peak_start"] == "16:00"