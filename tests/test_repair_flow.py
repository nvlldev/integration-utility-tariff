"""Test repair flow functionality."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResultType

from custom_components.utility_tariff.repairs import (
    XcelEnergyTariffRepairFlow,
    async_create_fix_flow,
    async_create_repair_issue,
)


async def test_repair_flow_retry(hass: HomeAssistant):
    """Test repair flow with retry option."""
    # Mock config entry
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.options = {"rate_schedule": "residential"}
    
    # Create repair flow
    flow = XcelEnergyTariffRepairFlow(config_entry)
    flow.hass = hass
    
    # Start flow
    result = await flow.async_step_init()
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pdf_error"
    
    # Choose retry
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        result = await flow.async_step_pdf_error({"action": "retry"})
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {}
        mock_reload.assert_called_once_with("test_entry")


async def test_repair_flow_manual_rates(hass: HomeAssistant):
    """Test repair flow with manual rate entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.options = {"rate_schedule": "residential"}
    
    flow = XcelEnergyTariffRepairFlow(config_entry)
    flow.hass = hass
    
    # Choose manual rates
    result = await flow.async_step_pdf_error({"action": "manual"})
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_rates"
    
    # Enter manual rates
    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            result = await flow.async_step_manual_rates({
                "base_rate": 0.12,
                "fixed_charge": 15.0
            })
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            
            # Check options were updated
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == config_entry
            assert call_args[1]["options"]["manual_rates"]["base_rate"] == 0.12
            assert call_args[1]["options"]["manual_rates"]["fixed_charge"] == 15.0
            assert call_args[1]["options"]["use_manual_rates"] is True


async def test_repair_flow_manual_rates_tou(hass: HomeAssistant):
    """Test repair flow with manual TOU rate entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.options = {"rate_schedule": "residential_tou"}
    
    flow = XcelEnergyTariffRepairFlow(config_entry)
    flow.hass = hass
    
    # Go to manual rates
    result = await flow.async_step_pdf_error({"action": "manual"})
    
    # Check TOU fields are present
    schema = result["data_schema"]
    schema_keys = [str(k) for k in schema.schema.keys()]
    
    assert "peak_rate" in schema_keys
    assert "off_peak_rate" in schema_keys
    assert "shoulder_rate" in schema_keys


async def test_repair_flow_fallback(hass: HomeAssistant):
    """Test repair flow with fallback option."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.options = {}
    
    flow = XcelEnergyTariffRepairFlow(config_entry)
    flow.hass = hass
    
    # Choose fallback
    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        result = await flow.async_step_pdf_error({"action": "fallback"})
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        
        # Check force_fallback was set
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[1]["options"]["force_fallback"] is True


async def test_repair_flow_alternative_url(hass: HomeAssistant):
    """Test repair flow with alternative URL."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.data = {"state": "CO", "service_type": "electric"}
    config_entry.options = {}
    
    flow = XcelEnergyTariffRepairFlow(config_entry)
    flow.hass = hass
    
    # Choose alternative URL
    result = await flow.async_step_pdf_error({"action": "alternative_url"})
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "alternative_url"
    assert "https://www.xcelenergy.com/staticfiles/CO-electric-tariff.pdf" in result["description_placeholders"]["example_url"]
    
    # Enter URL
    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            result = await flow.async_step_alternative_url({
                "pdf_url": "https://example.com/tariff.pdf"
            })
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            
            # Check URL was saved
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[1]["options"]["alternative_pdf_url"] == "https://example.com/tariff.pdf"


async def test_create_fix_flow(hass: HomeAssistant):
    """Test creating repair flow from issue data."""
    # Mock config entry
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    hass.config_entries.async_get_entry = MagicMock(return_value=config_entry)
    
    # Create flow with valid data
    flow = await async_create_fix_flow(
        hass,
        "pdf_error_test_entry",
        {"entry_id": "test_entry"}
    )
    
    assert isinstance(flow, XcelEnergyTariffRepairFlow)
    assert flow._entry == config_entry
    
    # Test with missing entry_id
    flow = await async_create_fix_flow(hass, "pdf_error", None)
    assert flow is None
    
    # Test with invalid entry_id
    hass.config_entries.async_get_entry.return_value = None
    flow = await async_create_fix_flow(
        hass,
        "pdf_error_invalid",
        {"entry_id": "invalid"}
    )
    assert flow is None


async def test_create_repair_issue(hass: HomeAssistant):
    """Test creating repair issue."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    config_entry.title = "Xcel Colorado Electric"
    
    with patch("custom_components.utility_tariff.repairs.ir.async_create_issue") as mock_create:
        async_create_repair_issue(
            hass,
            config_entry,
            "pdf_error",
            "Failed to parse PDF"
        )
        
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        
        assert call_args[0][0] == hass
        assert call_args[0][1] == "xcel_energy_tariff"
        assert call_args[0][2] == "pdf_error_test_entry"
        assert call_args[1]["is_fixable"] is True
        assert call_args[1]["translation_key"] == "pdf_error"
        assert call_args[1]["translation_placeholders"]["name"] == "Xcel Colorado Electric"
        assert call_args[1]["translation_placeholders"]["error"] == "Failed to parse PDF"
        assert call_args[1]["data"]["entry_id"] == "test_entry"