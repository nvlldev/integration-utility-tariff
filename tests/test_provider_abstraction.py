"""Tests for the provider abstraction layer."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.utility_tariff.providers import (
    ProviderDataExtractor,
    ProviderRateCalculator,
    ProviderDataSource,
    UtilityProvider,
    ProviderRegistry,
    ProviderTariffManager,
)


class MockDataExtractor(ProviderDataExtractor):
    """Mock data extractor for testing."""
    
    async def fetch_tariff_data(self, **kwargs):
        return {
            "rates": {"summer": 0.12, "winter": 0.10},
            "tou_rates": {
                "summer": {"peak": 0.25, "off_peak": 0.10},
                "winter": {"peak": 0.20, "off_peak": 0.08}
            },
            "fixed_charges": {"monthly_service": 15.00},
            "data_source": "mock",
        }
    
    def get_data_source_type(self):
        return "mock"
    
    def requires_file_download(self):
        return False
    
    async def validate_data(self, data):
        if not data.get("rates"):
            return False, "No rates found"
        return True, None


class MockRateCalculator(ProviderRateCalculator):
    """Mock rate calculator for testing."""
    
    def calculate_current_rate(self, time, tariff_data):
        if self.is_summer_season(time, {}):
            return tariff_data.get("rates", {}).get("summer", 0.12)
        return tariff_data.get("rates", {}).get("winter", 0.10)
    
    def get_tou_period(self, time, tariff_data):
        hour = time.hour
        if 15 <= hour < 19:
            return "Peak"
        return "Off-Peak"
    
    def is_summer_season(self, time, season_config):
        return time.month in [6, 7, 8, 9]
    
    def is_holiday(self, date, holiday_config):
        return False
    
    def get_all_current_rates(self, time, tariff_data):
        return tariff_data


class MockDataSource(ProviderDataSource):
    """Mock data source for testing."""
    
    def get_source_config(self, state, service_type, rate_schedule):
        return {
            "url": f"https://mock.com/{state}_{service_type}.pdf",
            "type": "mock"
        }
    
    def get_fallback_rates(self, state, service_type):
        return {
            "rates": {"summer": 0.11, "winter": 0.09},
            "fixed_charges": {"monthly_service": 12.00}
        }
    
    def supports_real_time_rates(self):
        return False
    
    def get_update_interval(self):
        return timedelta(days=1)


class MockProvider(UtilityProvider):
    """Mock provider for testing."""
    
    def __init__(self):
        super().__init__("mock_provider")
    
    @property
    def name(self):
        return "Mock Energy Company"
    
    @property
    def short_name(self):
        return "Mock"
    
    @property
    def supported_states(self):
        return {
            "electric": ["CA", "TX"],
            "gas": ["CA"]
        }
    
    @property
    def supported_rate_schedules(self):
        return {
            "electric": ["residential", "commercial"],
            "gas": ["residential_gas"]
        }
    
    @property
    def capabilities(self):
        return ["mock_data", "tou_rates", "seasonal_rates"]
    
    def _load_provider_config(self):
        return {"test": True}
    
    def _create_data_extractor(self):
        return MockDataExtractor()
    
    def _create_rate_calculator(self):
        return MockRateCalculator()
    
    def _create_data_source(self):
        return MockDataSource()


class TestProviderRegistry:
    """Test the provider registry."""
    
    def test_register_provider(self):
        """Test registering a provider."""
        # Clear registry first
        ProviderRegistry._providers = {}
        
        provider = MockProvider()
        ProviderRegistry.register_provider(provider)
        
        assert "mock_provider" in ProviderRegistry._providers
        assert ProviderRegistry.get_provider("mock_provider") == provider
    
    def test_get_all_providers(self):
        """Test getting all providers."""
        ProviderRegistry._providers = {}
        
        provider1 = MockProvider()
        provider1.provider_id = "provider1"
        provider2 = MockProvider()
        provider2.provider_id = "provider2"
        
        ProviderRegistry.register_provider(provider1)
        ProviderRegistry.register_provider(provider2)
        
        all_providers = ProviderRegistry.get_all_providers()
        assert len(all_providers) == 2
        assert "provider1" in all_providers
        assert "provider2" in all_providers
    
    def test_get_providers_for_state(self):
        """Test getting providers for a specific state."""
        ProviderRegistry._providers = {}
        
        provider = MockProvider()
        ProviderRegistry.register_provider(provider)
        
        # Test electric providers for CA
        ca_electric = ProviderRegistry.get_providers_for_state("CA", "electric")
        assert len(ca_electric) == 1
        assert ca_electric[0].provider_id == "mock_provider"
        
        # Test electric providers for unsupported state
        ny_electric = ProviderRegistry.get_providers_for_state("NY", "electric")
        assert len(ny_electric) == 0


class TestUtilityProvider:
    """Test the base utility provider."""
    
    def test_provider_initialization(self):
        """Test provider initialization."""
        provider = MockProvider()
        
        assert provider.provider_id == "mock_provider"
        assert provider.name == "Mock Energy Company"
        assert provider.short_name == "Mock"
        assert isinstance(provider.data_extractor, MockDataExtractor)
        assert isinstance(provider.rate_calculator, MockRateCalculator)
        assert isinstance(provider.data_source, MockDataSource)
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        provider = MockProvider()
        
        # Valid configuration
        assert provider.validate_configuration("CA", "electric", "residential")
        
        # Invalid state
        assert not provider.validate_configuration("NY", "electric", "residential")
        
        # Invalid service type
        assert not provider.validate_configuration("CA", "water", "residential")
        
        # Invalid rate schedule
        assert not provider.validate_configuration("CA", "electric", "industrial")


@pytest.mark.asyncio
class TestProviderTariffManager:
    """Test the provider tariff manager."""
    
    async def test_update_tariffs_success(self):
        """Test successful tariff update."""
        provider = MockProvider()
        hass = MagicMock()
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        result = await manager.async_update_tariffs()
        
        assert result is not None
        assert "rates" in result
        assert result["rates"]["summer"] == 0.12
        assert result["provider"] == "mock_provider"
        assert result["data_source_type"] == "mock"
    
    async def test_update_tariffs_fallback(self):
        """Test fallback when primary fetch fails."""
        provider = MockProvider()
        hass = MagicMock()
        
        # Make the extractor fail
        provider.data_extractor.fetch_tariff_data = AsyncMock(
            side_effect=Exception("Network error")
        )
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        result = await manager.async_update_tariffs()
        
        assert result is not None
        assert result["data_source"] == "fallback"
        assert result["rates"]["summer"] == 0.11  # Fallback rate
        assert "error" in result
    
    def test_get_current_rate(self):
        """Test getting current rate."""
        provider = MockProvider()
        hass = MagicMock()
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        # Set tariff data
        manager._tariff_data = {
            "rates": {"summer": 0.12, "winter": 0.10}
        }
        
        # Test summer rate
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 7, 15, 12, 0)
            rate = manager.get_current_rate()
            assert rate == 0.12
    
    def test_get_current_tou_period(self):
        """Test getting current TOU period."""
        provider = MockProvider()
        hass = MagicMock()
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric", 
            rate_schedule="residential",
            options={}
        )
        
        manager._tariff_data = {"tou_rates": {"summer": {"peak": 0.25}}}
        
        # Test peak period
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 7, 15, 16, 0)  # 4 PM
            period = manager.get_current_tou_period()
            assert period == "Peak"
    
    def test_supports_real_time_rates(self):
        """Test real-time rate support check."""
        provider = MockProvider()
        hass = MagicMock()
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        assert not manager.supports_real_time_rates()
    
    def test_update_interval(self):
        """Test update interval property."""
        provider = MockProvider()
        hass = MagicMock()
        
        manager = ProviderTariffManager(
            hass=hass,
            provider=provider,
            state="CA",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        assert manager.update_interval == timedelta(days=1)


class TestDataExtractor:
    """Test the data extractor interface."""
    
    @pytest.mark.asyncio
    async def test_extractor_interface(self):
        """Test that extractor implements required methods."""
        extractor = MockDataExtractor()
        
        # Test fetch_tariff_data
        data = await extractor.fetch_tariff_data(state="CA")
        assert "rates" in data
        
        # Test get_data_source_type
        assert extractor.get_data_source_type() == "mock"
        
        # Test requires_file_download
        assert not extractor.requires_file_download()
        
        # Test validate_data
        is_valid, error = await extractor.validate_data(data)
        assert is_valid
        assert error is None
        
        # Test validation failure
        is_valid, error = await extractor.validate_data({})
        assert not is_valid
        assert error == "No rates found"


class TestRateCalculator:
    """Test the rate calculator interface."""
    
    def test_calculator_interface(self):
        """Test that calculator implements required methods."""
        calculator = MockRateCalculator()
        tariff_data = {
            "rates": {"summer": 0.12, "winter": 0.10},
            "tou_rates": {
                "summer": {"peak": 0.25, "off_peak": 0.10}
            }
        }
        
        # Test calculate_current_rate
        summer_time = datetime(2024, 7, 15, 12, 0)
        rate = calculator.calculate_current_rate(summer_time, tariff_data)
        assert rate == 0.12
        
        winter_time = datetime(2024, 1, 15, 12, 0)
        rate = calculator.calculate_current_rate(winter_time, tariff_data)
        assert rate == 0.10
        
        # Test get_tou_period
        peak_time = datetime(2024, 7, 15, 16, 0)
        period = calculator.get_tou_period(peak_time, tariff_data)
        assert period == "Peak"
        
        off_peak_time = datetime(2024, 7, 15, 10, 0)
        period = calculator.get_tou_period(off_peak_time, tariff_data)
        assert period == "Off-Peak"
        
        # Test is_summer_season
        assert calculator.is_summer_season(summer_time, {})
        assert not calculator.is_summer_season(winter_time, {})
        
        # Test is_holiday
        assert not calculator.is_holiday(summer_time.date(), {})
        
        # Test get_all_current_rates
        all_rates = calculator.get_all_current_rates(summer_time, tariff_data)
        assert all_rates == tariff_data


class TestDataSource:
    """Test the data source interface."""
    
    def test_data_source_interface(self):
        """Test that data source implements required methods."""
        source = MockDataSource()
        
        # Test get_source_config
        config = source.get_source_config("CA", "electric", "residential")
        assert config["type"] == "mock"
        assert "url" in config
        
        # Test get_fallback_rates
        fallback = source.get_fallback_rates("CA", "electric")
        assert fallback["rates"]["summer"] == 0.11
        
        # Test supports_real_time_rates
        assert not source.supports_real_time_rates()
        
        # Test get_update_interval
        assert source.get_update_interval() == timedelta(days=1)