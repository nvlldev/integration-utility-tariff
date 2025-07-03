"""Test return entity and net metering functionality."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.utility_tariff.coordinator import DynamicCoordinator


@pytest.mark.asyncio
async def test_net_metering_calculations():
    """Test net metering calculations with consumption and return entities."""
    # Mock tariff manager
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.home_energy_usage",
        "return_entity": "sensor.solar_export",
        "average_daily_usage": 30.0
    }
    
    # Mock PDF coordinator
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    # Create dynamic coordinator
    coordinator = DynamicCoordinator(None, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock consumption entity (30 kWh daily)
    mock_consumption_state = MagicMock()
    mock_consumption_state.state = "30"
    mock_consumption_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Home Energy Usage Daily",
        "state_class": "total_increasing"
    }
    
    # Mock return entity (20 kWh daily solar export)
    mock_return_state = MagicMock()
    mock_return_state.state = "20"
    mock_return_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Solar Export Daily",
        "state_class": "total_increasing"
    }
    
    def mock_get_state(entity_id):
        if entity_id == "sensor.home_energy_usage":
            return mock_consumption_state
        elif entity_id == "sensor.solar_export":
            return mock_return_state
        return None
    
    with patch.object(coordinator, 'hass') as mock_hass:
        mock_hass.states.get = mock_get_state
        
        # Test cost calculation with net metering
        costs = coordinator._calculate_costs(0.10, {"fixed_charges": {"monthly_service": 10}})
        
        assert costs["available"] is True
        assert costs["daily_kwh_consumed"] == 30.0  # Gross consumption
        assert costs["daily_kwh_returned"] == 20.0  # Solar export
        assert costs["net_daily_kwh"] == 10.0  # Net consumption (30 - 20)
        assert costs["daily_kwh_used"] == 10.0  # Billable amount (only net consumption)
        assert costs["daily_cost_estimate"] == 1.0  # 10 kWh * $0.10
        assert costs["daily_credit_estimate"] == 0.0  # No excess export
        assert costs["consumption_source"] == "entity_daily_consumption"
        assert costs["return_source"] == "entity_daily_return"


@pytest.mark.asyncio
async def test_excess_solar_export():
    """Test calculations when solar export exceeds consumption."""
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.home_energy_usage",
        "return_entity": "sensor.solar_export",
        "average_daily_usage": 30.0
    }
    
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    coordinator = DynamicCoordinator(None, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock consumption entity (25 kWh daily)
    mock_consumption_state = MagicMock()
    mock_consumption_state.state = "25"
    mock_consumption_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Home Energy Usage Daily"
    }
    
    # Mock return entity (35 kWh daily - more than consumption)
    mock_return_state = MagicMock()
    mock_return_state.state = "35"
    mock_return_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Solar Export Daily"
    }
    
    def mock_get_state(entity_id):
        if entity_id == "sensor.home_energy_usage":
            return mock_consumption_state
        elif entity_id == "sensor.solar_export":
            return mock_return_state
        return None
    
    with patch.object(coordinator, 'hass') as mock_hass:
        mock_hass.states.get = mock_get_state
        
        costs = coordinator._calculate_costs(0.12, {"fixed_charges": {"monthly_service": 15}})
        
        assert costs["daily_kwh_consumed"] == 25.0
        assert costs["daily_kwh_returned"] == 35.0
        assert costs["net_daily_kwh"] == -10.0  # Net export (25 - 35)
        assert costs["daily_kwh_used"] == 0.0  # No billable consumption
        assert costs["daily_cost_estimate"] == 0.0  # No cost for net export
        assert costs["daily_credit_estimate"] == 1.2  # 10 kWh excess * $0.12
        assert costs["monthly_cost_estimate"] == 15.0  # Only fixed charges


@pytest.mark.asyncio
async def test_no_return_entity():
    """Test calculations without return entity (no solar)."""
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.home_energy_usage",
        "return_entity": "none",
        "average_daily_usage": 30.0
    }
    
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    coordinator = DynamicCoordinator(None, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock consumption entity only
    mock_consumption_state = MagicMock()
    mock_consumption_state.state = "35"
    mock_consumption_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Home Energy Usage Daily"
    }
    
    def mock_get_state(entity_id):
        if entity_id == "sensor.home_energy_usage":
            return mock_consumption_state
        return None
    
    with patch.object(coordinator, 'hass') as mock_hass:
        mock_hass.states.get = mock_get_state
        
        costs = coordinator._calculate_costs(0.08, {"fixed_charges": {"monthly_service": 12}})
        
        assert costs["daily_kwh_consumed"] == 35.0
        assert costs["daily_kwh_returned"] == 0.0  # No return
        assert costs["net_daily_kwh"] == 35.0  # Same as consumption
        assert costs["daily_kwh_used"] == 35.0  # All consumption is billable
        assert costs["daily_cost_estimate"] == 2.8  # 35 kWh * $0.08
        assert costs["daily_credit_estimate"] == 0.0  # No credits
        assert costs["return_source"] == "none"


@pytest.mark.asyncio
async def test_return_entity_unavailable():
    """Test handling when return entity is unavailable."""
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.home_energy_usage",
        "return_entity": "sensor.solar_export",
        "average_daily_usage": 30.0
    }
    
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    coordinator = DynamicCoordinator(None, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock consumption entity
    mock_consumption_state = MagicMock()
    mock_consumption_state.state = "28"
    mock_consumption_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Home Energy Usage Daily"
    }
    
    # Mock unavailable return entity
    mock_return_state = MagicMock()
    mock_return_state.state = "unavailable"
    
    def mock_get_state(entity_id):
        if entity_id == "sensor.home_energy_usage":
            return mock_consumption_state
        elif entity_id == "sensor.solar_export":
            return mock_return_state
        return None
    
    with patch.object(coordinator, 'hass') as mock_hass:
        mock_hass.states.get = mock_get_state
        
        costs = coordinator._calculate_costs(0.09, {"fixed_charges": {"monthly_service": 8}})
        
        assert costs["daily_kwh_consumed"] == 28.0
        assert costs["daily_kwh_returned"] == 0.0  # Falls back to 0 when unavailable
        assert costs["net_daily_kwh"] == 28.0
        assert costs["return_source"] == "unavailable"


@pytest.mark.asyncio
async def test_mixed_units_conversion():
    """Test unit conversion for mixed kWh/Wh sensors."""
    mock_tariff_manager = MagicMock()
    mock_tariff_manager.options = {
        "consumption_entity": "sensor.consumption_wh",
        "return_entity": "sensor.export_kwh",
        "average_daily_usage": 30.0
    }
    
    mock_pdf_coordinator = MagicMock()
    mock_pdf_coordinator.data = {}
    
    coordinator = DynamicCoordinator(None, mock_tariff_manager, mock_pdf_coordinator)
    
    # Mock consumption in Wh
    mock_consumption_state = MagicMock()
    mock_consumption_state.state = "25000"  # 25000 Wh = 25 kWh
    mock_consumption_state.attributes = {
        "unit_of_measurement": "Wh",
        "friendly_name": "Home Energy Usage Daily"
    }
    
    # Mock return in kWh
    mock_return_state = MagicMock()
    mock_return_state.state = "15"  # 15 kWh
    mock_return_state.attributes = {
        "unit_of_measurement": "kWh",
        "friendly_name": "Solar Export Daily"
    }
    
    def mock_get_state(entity_id):
        if entity_id == "sensor.consumption_wh":
            return mock_consumption_state
        elif entity_id == "sensor.export_kwh":
            return mock_return_state
        return None
    
    with patch.object(coordinator, 'hass') as mock_hass:
        mock_hass.states.get = mock_get_state
        
        costs = coordinator._calculate_costs(0.11, {})
        
        assert costs["daily_kwh_consumed"] == 25.0  # Converted from Wh
        assert costs["daily_kwh_returned"] == 15.0  # Already in kWh
        assert costs["net_daily_kwh"] == 10.0  # 25 - 15