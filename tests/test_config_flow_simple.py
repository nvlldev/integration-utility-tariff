"""Simple tests for Xcel Energy Tariff config flow validation."""
import pytest
from unittest.mock import Mock

from custom_components.xcel_energy_tariff.config_flow import validate_input


class TestConfigFlowValidation:
    """Test config flow validation logic."""

    def test_validate_input_valid(self):
        """Test validation with valid input."""
        mock_hass = Mock()
        
        # Valid state and service combination
        result = validate_input(mock_hass, {
            "state": "CO",
            "service_type": "electric",
            "rate_schedule": "residential_tou",
        })
        
        assert result["title"] == "Xcel Energy Colorado Electric"

    def test_validate_input_invalid_state(self):
        """Test validation with invalid state."""
        mock_hass = Mock()
        
        # Invalid state
        with pytest.raises(ValueError, match="Invalid state selected"):
            validate_input(mock_hass, {
                "state": "ZZ",
                "service_type": "electric",
                "rate_schedule": "residential",
            })

    def test_validate_input_gas_not_available(self):
        """Test validation when gas is not available in state."""
        mock_hass = Mock()
        
        # Texas doesn't have gas in our configuration
        with pytest.raises(ValueError, match="Gas service not available"):
            validate_input(mock_hass, {
                "state": "TX",
                "service_type": "gas",
                "rate_schedule": "residential",
            })