"""Test fallback rates for all states."""
import pytest
from unittest.mock import Mock
from custom_components.xcel_energy_tariff.tariff_manager import XcelTariffManager
from custom_components.xcel_energy_tariff.const import STATES


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.config.path.return_value = "/tmp/test"
    return hass


class TestFallbackRates:
    """Test fallback rates for all Xcel Energy states."""
    
    def test_electric_residential_rates_all_states(self, mock_hass):
        """Test that all states have proper residential electric fallback rates."""
        for state_code in STATES.keys():
            manager = XcelTariffManager(mock_hass, state_code, "electric", "residential")
            fallback = manager._get_fallback_rates()
            
            # Verify rates exist
            assert "rates" in fallback
            assert len(fallback["rates"]) > 0
            
            # Verify fixed charges exist
            assert "fixed_charges" in fallback
            assert "monthly_service" in fallback["fixed_charges"]
            assert fallback["fixed_charges"]["monthly_service"] > 0
            
            # Verify rates are reasonable (between $0.05 and $0.20/kWh)
            for rate_type, rate_value in fallback["rates"].items():
                assert 0.05 <= rate_value <= 0.20, f"{state_code} {rate_type} rate {rate_value} out of range"
    
    def test_electric_tou_rates_all_states(self, mock_hass):
        """Test that all states have proper TOU electric fallback rates."""
        for state_code in STATES.keys():
            manager = XcelTariffManager(mock_hass, state_code, "electric", "residential_tou")
            fallback = manager._get_fallback_rates()
            
            # Verify TOU rates exist
            assert "tou_rates" in fallback
            assert "summer" in fallback["tou_rates"]
            assert "winter" in fallback["tou_rates"]
            
            # Verify all TOU periods have rates
            for season in ["summer", "winter"]:
                assert "peak" in fallback["tou_rates"][season]
                assert "off_peak" in fallback["tou_rates"][season]
                
                # Verify peak > off-peak
                assert fallback["tou_rates"][season]["peak"] > fallback["tou_rates"][season]["off_peak"]
                
                # Verify rates are reasonable
                assert 0.05 <= fallback["tou_rates"][season]["off_peak"] <= 0.15
                # Adjusted for actual Colorado rates which are lower
                assert 0.08 <= fallback["tou_rates"][season]["peak"] <= 0.30
            
            # Verify TOU schedule exists
            assert "tou_schedule" in fallback
            assert "season_months" in fallback["tou_schedule"]
            assert "summer" in fallback["tou_schedule"]["season_months"]
            assert "winter" in fallback["tou_schedule"]["season_months"]
            
            # Verify all months are accounted for
            all_months = set(fallback["tou_schedule"]["season_months"]["summer"] + 
                           fallback["tou_schedule"]["season_months"]["winter"])
            assert all_months == set(range(1, 13))
    
    def test_gas_rates_all_states(self, mock_hass):
        """Test that all states have proper gas fallback rates."""
        for state_code in STATES.keys():
            manager = XcelTariffManager(mock_hass, state_code, "gas", "residential")
            fallback = manager._get_fallback_rates()
            
            # Verify rates exist
            assert "rates" in fallback
            assert "standard" in fallback["rates"]
            
            # Verify fixed charges exist
            assert "fixed_charges" in fallback
            assert "monthly_service" in fallback["fixed_charges"]
            
            # Verify gas rates are reasonable (between $0.40 and $1.00/therm)
            assert 0.40 <= fallback["rates"]["standard"] <= 1.00
            assert 5.00 <= fallback["fixed_charges"]["monthly_service"] <= 20.00
    
    def test_commercial_demand_charges_all_states(self, mock_hass):
        """Test that all states have proper commercial demand charges."""
        for state_code in STATES.keys():
            manager = XcelTariffManager(mock_hass, state_code, "electric", "commercial")
            fallback = manager._get_fallback_rates()
            
            # Verify demand charges exist
            assert "demand_charges" in fallback
            assert "per_kw" in fallback["demand_charges"]
            assert "minimum_demand" in fallback["demand_charges"]
            
            # Verify demand charges are reasonable
            assert 10.00 <= fallback["demand_charges"]["per_kw"] <= 20.00
            assert 30.00 <= fallback["demand_charges"]["minimum_demand"] <= 60.00
    
    def test_state_specific_variations(self, mock_hass):
        """Test that different states have different rates."""
        # Compare Colorado and Texas rates
        co_manager = XcelTariffManager(mock_hass, "CO", "electric", "residential")
        tx_manager = XcelTariffManager(mock_hass, "TX", "electric", "residential")
        
        co_fallback = co_manager._get_fallback_rates()
        tx_fallback = tx_manager._get_fallback_rates()
        
        # Rates should be different between states
        assert co_fallback["rates"] != tx_fallback["rates"]
        assert co_fallback["fixed_charges"] != tx_fallback["fixed_charges"]