"""Test fallback rates for all states."""
import pytest
from unittest.mock import Mock
from custom_components.utility_tariff.tariff_manager import GenericTariffManager
from custom_components.utility_tariff.const import ALL_STATES as STATES
from custom_components.utility_tariff.providers import UtilityProvider


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.config.path.return_value = "/tmp/test"
    return hass


@pytest.fixture 
def mock_provider():
    """Create a mock utility provider."""
    provider = Mock(spec=UtilityProvider)
    provider.name = "Test Utility"
    provider.supports_gas = True
    provider.supports_electric = True
    # Mock the validate_configuration method to return valid configuration
    provider.validate_configuration.return_value = (True, None)
    return provider


class TestFallbackRates:
    """Test fallback rates for all utility provider states."""
    
    def test_electric_residential_rates_all_states(self, mock_hass, mock_provider):
        """Test that all states have proper residential electric fallback rates."""
        for state_code in STATES.keys():
            manager = GenericTariffManager(
                mock_hass, 
                mock_provider,
                state_code, 
                "electric", 
                "residential",
                {}  # Empty options
            )
            fallback = manager._provider_manager._get_fallback_rates()
            
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
    
    def test_electric_tou_rates_all_states(self, mock_hass, mock_provider):
        """Test that all states have proper TOU electric fallback rates."""
        for state_code in STATES.keys():
            manager = GenericTariffManager(
                mock_hass,
                mock_provider,
                state_code,
                "electric",
                "residential_tou",
                {}
            )
            fallback = manager._provider_manager._get_fallback_rates()
            
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
                # Adjusted for actual rates which can vary significantly
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
    
    def test_gas_rates_all_states(self, mock_hass, mock_provider):
        """Test that all states have proper gas fallback rates."""
        for state_code in STATES.keys():
            manager = GenericTariffManager(
                mock_hass,
                mock_provider,
                state_code,
                "gas",
                "residential",
                {}
            )
            fallback = manager._provider_manager._get_fallback_rates()
            
            # Verify rates exist
            assert "rates" in fallback
            assert len(fallback["rates"]) > 0
            
            # Verify fixed charges exist
            assert "fixed_charges" in fallback
            assert "monthly_service" in fallback["fixed_charges"]
            assert fallback["fixed_charges"]["monthly_service"] > 0
            
            # Verify rates are reasonable (between $0.50 and $2.00/therm)
            for rate_type, rate_value in fallback["rates"].items():
                assert 0.50 <= rate_value <= 2.00, f"{state_code} {rate_type} rate {rate_value} out of range"
    
    def test_commercial_demand_charges_all_states(self, mock_hass, mock_provider):
        """Test that commercial rates have demand charges."""
        for state_code in STATES.keys():
            manager = GenericTariffManager(
                mock_hass,
                mock_provider,
                state_code,
                "electric",
                "commercial",
                {}
            )
            fallback = manager._provider_manager._get_fallback_rates()
            
            # Verify demand charges exist for commercial
            assert "demand_charges" in fallback
            assert fallback["demand_charges"]["demand_charge_kw"] > 0
    
    def test_state_specific_variations(self, mock_hass, mock_provider):
        """Test that different states have different rates."""
        rates_by_state = {}
        
        for state_code in STATES.keys():
            manager = GenericTariffManager(
                mock_hass,
                mock_provider,
                state_code,
                "electric",
                "residential",
                {}
            )
            fallback = manager._provider_manager._get_fallback_rates()
            rates_by_state[state_code] = fallback["rates"].get("standard", 0)
        
        # Verify that not all states have identical rates
        unique_rates = set(rates_by_state.values())
        assert len(unique_rates) > 1, "All states have identical rates, which is unlikely"