"""Integration tests for the generic Utility Tariff integration."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.utility_tariff import async_setup_entry, async_unload_entry
from custom_components.utility_tariff.const import DOMAIN


class TestUtilityTariffIntegration:
    """Test the Utility Tariff integration."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        return ConfigEntry(
            domain=DOMAIN,
            title="PG&E California",
            data={
                "provider": "pge",
                "state": "CA",
                "service_type": "electric",
                "rate_schedule": "E-1",
            },
            options={
                "update_frequency": "daily",
                "enable_cost_sensors": True,
                "average_daily_usage": 30.0,
            },
            entry_id="test_entry_id",
            version=3,
        )

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = Mock()
        provider.provider_id = "pge"
        provider.name = "Pacific Gas & Electric"
        provider.short_name = "PG&E"
        provider.supported_states = {"electric": ["CA"], "gas": ["CA"]}
        provider.supported_rate_schedules = {"electric": ["E-1", "E-6"], "gas": ["GS-1"]}
        provider.validate_configuration = Mock(return_value=True)
        
        # Mock data extractor
        extractor = AsyncMock()
        extractor.fetch_tariff_data = AsyncMock(return_value={
            "rates": {"summer": 0.25, "winter": 0.20},
            "tou_rates": {
                "summer": {"peak": 0.45, "part_peak": 0.35, "off_peak": 0.25},
                "winter": {"peak": 0.35, "part_peak": 0.30, "off_peak": 0.25}
            },
            "fixed_charges": {"monthly_service": 10.00},
            "data_source": "api",
        })
        extractor.get_data_source_type = Mock(return_value="api")
        extractor.validate_data = AsyncMock(return_value=(True, None))
        provider.data_extractor = extractor
        
        # Mock rate calculator
        calculator = Mock()
        calculator.calculate_current_rate = Mock(return_value=0.25)
        calculator.get_tou_period = Mock(return_value="Off-Peak")
        calculator.is_summer_season = Mock(return_value=True)
        calculator.is_holiday = Mock(return_value=False)
        calculator.get_all_current_rates = Mock(return_value={
            "rates": {"summer": 0.25},
            "tou_rates": {"summer": {"off_peak": 0.25}},
            "fixed_charges": {"monthly_service": 10.00}
        })
        provider.rate_calculator = calculator
        
        # Mock data source
        data_source = Mock()
        data_source.get_source_config = Mock(return_value={
            "type": "api",
            "api_endpoint": "https://api.pge.com/rates",
        })
        data_source.get_fallback_rates = Mock(return_value={
            "rates": {"summer": 0.24, "winter": 0.19},
            "fixed_charges": {"monthly_service": 9.50}
        })
        data_source.get_update_interval = Mock(return_value=timedelta(hours=1))
        data_source.supports_real_time_rates = Mock(return_value=False)
        provider.data_source = data_source
        
        return provider

    @pytest.fixture
    def mock_providers(self, mock_provider):
        """Mock the provider registry."""
        providers = {"pge": mock_provider}
        
        with patch("custom_components.utility_tariff.initialize_providers"):
            with patch("custom_components.utility_tariff.get_available_providers", return_value=providers):
                yield providers

    @pytest.mark.asyncio
    async def test_setup_entry(self, hass: HomeAssistant, mock_config_entry, mock_providers):
        """Test setting up the integration."""
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        
        # Setup the integration
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is True
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        
        # Check that required components are initialized
        entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "tariff_manager" in entry_data
        assert "pdf_coordinator" in entry_data
        assert "dynamic_coordinator" in entry_data
        assert "provider" in entry_data
        
        # Verify provider is correct
        assert entry_data["provider"].provider_id == "pge"
        
        # Verify platforms are set up
        hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_config_entry, [Platform.SENSOR]
        )

    @pytest.mark.asyncio
    async def test_setup_entry_invalid_provider(self, hass: HomeAssistant, mock_config_entry):
        """Test setup fails with invalid provider."""
        mock_config_entry.data = {
            **mock_config_entry.data,
            "provider": "invalid_provider"
        }
        
        with patch("custom_components.utility_tariff.initialize_providers"):
            with patch("custom_components.utility_tariff.get_available_providers", return_value={}):
                result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_setup_entry_invalid_configuration(self, hass: HomeAssistant, mock_config_entry, mock_providers):
        """Test setup fails with invalid configuration."""
        # Make validation fail
        mock_providers["pge"].validate_configuration.return_value = False
        
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_unload_entry(self, hass: HomeAssistant, mock_config_entry, mock_providers):
        """Test unloading the integration."""
        # First set up the integration
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        await async_setup_entry(hass, mock_config_entry)
        
        # Now unload it
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        result = await async_unload_entry(hass, mock_config_entry)
        
        assert result is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_migrate_entry_from_v1(self, hass: HomeAssistant):
        """Test migrating from version 1 (Xcel-only) to version 3 (multi-provider)."""
        from custom_components.utility_tariff import async_migrate_entry
        
        # Create an old version 1 entry (no provider field)
        old_entry = ConfigEntry(
            domain=DOMAIN,
            title="Xcel Energy Colorado",
            data={
                "state": "CO",
                "service_type": "electric",
                "rate_schedule": "residential",
            },
            version=1,
            entry_id="old_entry_id",
        )
        
        # Mock the update method
        hass.config_entries.async_update_entry = Mock()
        
        # Run migration
        result = await async_migrate_entry(hass, old_entry)
        
        assert result is True
        assert old_entry.version == 3
        
        # Verify provider was added
        hass.config_entries.async_update_entry.assert_called_once()
        call_args = hass.config_entries.async_update_entry.call_args
        assert call_args[0][0] == old_entry
        assert call_args[1]["data"]["provider"] == "xcel_energy"

    @pytest.mark.asyncio
    async def test_coordinator_updates(self, hass: HomeAssistant, mock_config_entry, mock_providers):
        """Test that coordinators update correctly."""
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        
        # Setup the integration
        await async_setup_entry(hass, mock_config_entry)
        
        entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        pdf_coordinator = entry_data["pdf_coordinator"]
        dynamic_coordinator = entry_data["dynamic_coordinator"]
        
        # Test PDF coordinator update
        with patch.object(pdf_coordinator.tariff_manager, 'async_update_tariffs', 
                         new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {
                "rates": {"summer": 0.25},
                "data_source": "api"
            }
            
            await pdf_coordinator._async_update_data()
            mock_update.assert_called_once()
            
        # Test dynamic coordinator update
        await dynamic_coordinator._async_update_data()
        
        # Verify data is calculated
        assert dynamic_coordinator.data is not None
        assert "current_rate" in dynamic_coordinator.data
        assert "current_period" in dynamic_coordinator.data
        assert dynamic_coordinator.data["current_rate"] == 0.25

    @pytest.mark.asyncio
    async def test_multi_provider_support(self, hass: HomeAssistant):
        """Test that multiple providers can be registered and used."""
        from custom_components.utility_tariff.providers import ProviderRegistry
        
        # Clear registry
        ProviderRegistry._providers = {}
        
        # Create multiple mock providers
        providers = {}
        for provider_id in ["pge", "coned", "duke"]:
            provider = Mock()
            provider.provider_id = provider_id
            provider.name = f"{provider_id.upper()} Energy"
            provider.supported_states = {"electric": ["CA", "NY", "NC"]}
            providers[provider_id] = provider
            ProviderRegistry.register_provider(provider)
        
        # Verify all providers are registered
        all_providers = ProviderRegistry.get_all_providers()
        assert len(all_providers) == 3
        assert "pge" in all_providers
        assert "coned" in all_providers
        assert "duke" in all_providers
        
        # Test getting providers for specific state
        ca_providers = ProviderRegistry.get_providers_for_state("CA", "electric")
        assert len(ca_providers) == 3  # All support CA in this test

    def test_entity_naming_with_provider(self, mock_config_entry, mock_provider):
        """Test that entities are named correctly with provider short name."""
        from custom_components.utility_tariff.sensor import UtilityCurrentRateSensor
        
        # Create mock coordinator
        coordinator = Mock()
        coordinator.data = {"current_rate": 0.25}
        coordinator.hass = Mock()
        coordinator.hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "provider": mock_provider
                }
            }
        }
        
        # Create sensor
        sensor = UtilityCurrentRateSensor(coordinator, mock_config_entry)
        
        # Verify naming includes provider short name
        assert "PG&E" in sensor.name
        assert "California" in sensor.name
        assert "Current Rate" in sensor.name

    @pytest.mark.asyncio
    async def test_fallback_rates(self, hass: HomeAssistant, mock_config_entry, mock_providers):
        """Test fallback rates are used when primary fetch fails."""
        # Make primary fetch fail
        mock_providers["pge"].data_extractor.fetch_tariff_data.side_effect = Exception("API Error")
        
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        await async_setup_entry(hass, mock_config_entry)
        
        entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        tariff_manager = entry_data["tariff_manager"]
        
        # Update should use fallback rates
        result = await tariff_manager._provider_manager.async_update_tariffs()
        
        assert result is not None
        assert result["data_source"] == "fallback"
        assert result["rates"]["summer"] == 0.24  # Fallback rate
        assert "error" in result