"""Provider abstraction layer for utility rate integrations."""

from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ProviderDataExtractor(ABC):
    """Abstract base class for provider-specific data extraction.
    
    This could extract from PDFs, APIs, HTML pages, CSV files, etc.
    """
    
    @abstractmethod
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch and extract all tariff data from the provider's source.
        
        Returns a standardized dictionary containing:
        - rates: Base energy rates
        - tou_rates: Time-of-use rates (if applicable)
        - fixed_charges: Monthly service charges
        - tou_schedule: TOU period definitions
        - season_definitions: Summer/winter months
        - effective_date: When rates became effective
        - data_source: Where the data came from (pdf, api, html, etc.)
        - raw_data: Optional raw data for debugging
        """
        pass
    
    @abstractmethod
    def get_data_source_type(self) -> str:
        """Return the type of data source (pdf, api, html, csv, etc.)."""
        pass
    
    @abstractmethod
    def requires_file_download(self) -> bool:
        """Whether this extractor needs to download files."""
        pass
    
    @abstractmethod
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate extracted data. Returns (is_valid, error_message)."""
        pass


class ProviderRateCalculator(ABC):
    """Abstract base class for provider-specific rate calculations."""
    
    @abstractmethod
    def calculate_current_rate(self, time: datetime, tariff_data: Dict[str, Any]) -> Optional[float]:
        """Calculate current rate for given time and tariff data."""
        pass
    
    @abstractmethod
    def get_tou_period(self, time: datetime, tariff_data: Dict[str, Any]) -> str:
        """Get current TOU period for given time."""
        pass
    
    @abstractmethod
    def is_summer_season(self, time: datetime, season_config: Dict[str, Any]) -> bool:
        """Determine if given time is in summer season."""
        pass
    
    @abstractmethod
    def is_holiday(self, date: date, holiday_config: Dict[str, Any]) -> bool:
        """Determine if given date is a holiday."""
        pass
    
    @abstractmethod
    def get_all_current_rates(self, time: datetime, tariff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all current rates and charges for given time."""
        pass


class ProviderDataSource(ABC):
    """Abstract base class for provider data source configuration."""
    
    @abstractmethod
    def get_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        """Get configuration for accessing the data source.
        
        Could return:
        - url: For PDF/HTML downloads
        - api_endpoint: For REST APIs
        - api_key: For authenticated APIs
        - file_path: For local files
        - etc.
        """
        pass
    
    @abstractmethod
    def get_fallback_rates(self, state: str, service_type: str) -> Dict[str, Any]:
        """Get fallback rates for given state and service type."""
        pass
    
    @abstractmethod
    def supports_real_time_rates(self) -> bool:
        """Whether this provider supports real-time rate updates."""
        pass
    
    @abstractmethod
    def get_update_interval(self) -> timedelta:
        """Get recommended update interval for this data source."""
        pass


class UtilityProvider(ABC):
    """Base class for utility providers."""
    
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self.config = self._load_provider_config()
        self.data_extractor = self._create_data_extractor()
        self.rate_calculator = self._create_rate_calculator()
        self.data_source = self._create_data_source()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
        pass
    
    @property
    @abstractmethod
    def short_name(self) -> str:
        """Provider short name for entity naming."""
        pass
    
    @property
    @abstractmethod
    def supported_states(self) -> Dict[str, List[str]]:
        """States/regions supported by this provider, keyed by service type."""
        pass
    
    @property
    @abstractmethod
    def supported_rate_schedules(self) -> Dict[str, List[str]]:
        """Rate schedules supported by this provider, keyed by service type."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of provider capabilities."""
        pass
    
    @abstractmethod
    def _load_provider_config(self) -> Dict[str, Any]:
        """Load provider-specific configuration."""
        pass
    
    @abstractmethod
    def _create_data_extractor(self) -> ProviderDataExtractor:
        """Create provider-specific data extractor."""
        pass
    
    @abstractmethod
    def _create_rate_calculator(self) -> ProviderRateCalculator:
        """Create provider-specific rate calculator."""
        pass
    
    @abstractmethod
    def _create_data_source(self) -> ProviderDataSource:
        """Create provider-specific data source configuration."""
        pass
    
    def validate_configuration(self, state: str, service_type: str, rate_schedule: str) -> Tuple[bool, Optional[str]]:
        """Validate that the configuration is supported by this provider.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate inputs are provided
        if not state:
            return False, "State is required"
        if not service_type:
            return False, "Service type is required"
        if not rate_schedule:
            return False, "Rate schedule is required"
        
        # Validate service type is supported
        if service_type not in self.supported_states:
            return False, f"Service type '{service_type}' is not supported by {self.name}"
        
        # Validate state is supported for this service type
        if state not in self.supported_states[service_type]:
            supported = ", ".join(self.supported_states[service_type])
            return False, f"{self.name} does not support {service_type} service in {state}. Supported states: {supported}"
        
        # Validate rate schedule is supported
        if service_type not in self.supported_rate_schedules:
            return False, f"No rate schedules defined for {service_type} service"
        
        if rate_schedule not in self.supported_rate_schedules[service_type]:
            supported = ", ".join(self.supported_rate_schedules[service_type])
            return False, f"Rate schedule '{rate_schedule}' is not supported. Available schedules: {supported}"
        
        return True, None


class ProviderRegistry:
    """Registry for utility providers."""
    
    _providers: Dict[str, UtilityProvider] = {}
    
    @classmethod
    def register_provider(cls, provider: UtilityProvider) -> None:
        """Register a utility provider."""
        cls._providers[provider.provider_id] = provider
    
    @classmethod
    def get_provider(cls, provider_id: str) -> Optional[UtilityProvider]:
        """Get a registered provider by ID."""
        return cls._providers.get(provider_id)
    
    @classmethod
    def get_all_providers(cls) -> Dict[str, UtilityProvider]:
        """Get all registered providers."""
        return cls._providers.copy()
    
    @classmethod
    def get_providers_for_state(cls, state: str, service_type: str) -> List[UtilityProvider]:
        """Get all providers that support the given state and service type."""
        return [
            provider for provider in cls._providers.values()
            if service_type in provider.supported_states
            and state in provider.supported_states[service_type]
        ]


class ProviderTariffManager:
    """Generic tariff manager that delegates to provider-specific implementations."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        provider: UtilityProvider,
        state: str,
        service_type: str,
        rate_schedule: str,
        options: Dict[str, Any]
    ):
        self.hass = hass
        self.provider = provider
        self.state = state
        self.service_type = service_type
        self.rate_schedule = rate_schedule
        self.options = options
        self._tariff_data: Dict[str, Any] = {}
        
        # Validate configuration on init
        is_valid, error_msg = provider.validate_configuration(state, service_type, rate_schedule)
        if not is_valid:
            raise ValueError(f"Invalid configuration: {error_msg}")
    
    async def async_update_tariffs(self) -> Dict[str, Any]:
        """Update tariff data from provider source."""
        try:
            # Get the data source configuration
            source_config = self.provider.data_source.get_source_config(
                self.state, self.service_type, self.rate_schedule
            )
            
            # Get the appropriate extractor based on data source type
            # This allows providers to use different extractors for different states/configs
            extractor = self._get_appropriate_extractor(source_config)
            
            # Build parameters for the extractor
            params = {
                "state": self.state,
                "service_type": self.service_type,
                "rate_schedule": self.rate_schedule,
                **source_config  # Add all source-specific config
            }
            
            # Fetch data using provider-specific method
            tariff_data = await extractor.fetch_tariff_data(**params)
            
            # Validate the data
            is_valid, error_msg = await extractor.validate_data(tariff_data)
            if not is_valid:
                raise ValueError(f"Invalid tariff data: {error_msg}")
            
            # Additional validation
            if not isinstance(tariff_data, dict):
                raise ValueError("Tariff data must be a dictionary")
            
            # Ensure required fields are present
            if not tariff_data.get("rates") and not tariff_data.get("tou_rates"):
                raise ValueError("Tariff data must contain either 'rates' or 'tou_rates'")
            
            # Validate rate values are numeric and positive
            if "rates" in tariff_data:
                for rate_key, rate_value in tariff_data["rates"].items():
                    if rate_value is not None and (not isinstance(rate_value, (int, float)) or rate_value < 0):
                        raise ValueError(f"Invalid rate value for {rate_key}: {rate_value}")
            
            # Add metadata
            tariff_data.update({
                "last_updated": datetime.now().isoformat(),
                "provider": self.provider.provider_id,
                "data_source_type": extractor.get_data_source_type(),
            })
            
            self._tariff_data = tariff_data
            return self._tariff_data
            
        except Exception as e:
            _LOGGER.warning(
                "Failed to fetch tariff data from %s source: %s. Attempting fallback rates.",
                self.provider.name, str(e)
            )
            
            # Fall back to provider fallback rates
            try:
                fallback_data = self.provider.data_source.get_fallback_rates(
                    self.state, self.service_type
                )
                if fallback_data:
                    self._tariff_data = {
                        **fallback_data,
                        "provider": self.provider.provider_id,
                        "data_source": "fallback",
                        "error": str(e),
                        "last_updated": datetime.now().isoformat(),
                    }
                    _LOGGER.info(
                        "Using fallback rates for %s %s %s",
                        self.provider.name, self.state, self.service_type
                    )
                    return self._tariff_data
                else:
                    _LOGGER.error(
                        "No fallback rates available for %s %s %s",
                        self.provider.name, self.state, self.service_type
                    )
            except Exception as fallback_error:
                _LOGGER.error(
                    "Failed to get fallback rates: %s",
                    str(fallback_error)
                )
            
            # Re-raise original error if no fallback available
            raise
    
    def get_current_rate(self) -> Optional[float]:
        """Get current rate using provider calculator."""
        if not self._tariff_data:
            return None
        
        try:
            rate = self.provider.rate_calculator.calculate_current_rate(
                datetime.now(), self._tariff_data
            )
            
            # Validate rate is reasonable
            if rate is not None:
                if not isinstance(rate, (int, float)):
                    _LOGGER.error("Rate calculator returned non-numeric value: %s", rate)
                    return None
                if rate < 0:
                    _LOGGER.error("Rate calculator returned negative rate: %s", rate)
                    return None
                if rate > 10:  # $10/kWh would be extremely high
                    _LOGGER.warning("Rate calculator returned unusually high rate: %s", rate)
            
            return rate
        except Exception as e:
            _LOGGER.error("Error calculating current rate: %s", str(e))
            return None
    
    def get_current_tou_period(self) -> str:
        """Get current TOU period using provider calculator."""
        if not self._tariff_data:
            return "Unknown"
        period = self.provider.rate_calculator.get_tou_period(
            datetime.now(), self._tariff_data
        )
        _LOGGER.debug("Provider manager returning TOU period: %s", period)
        return period
    
    def is_summer_season(self, time: datetime) -> bool:
        """Check if time is in summer season using provider calculator."""
        season_config = self._tariff_data.get("season_definitions", {})
        return self.provider.rate_calculator.is_summer_season(time, season_config)
    
    def is_holiday(self, date: date) -> bool:
        """Check if date is a holiday using provider calculator."""
        holiday_config = self.provider.config.get("holidays", {})
        return self.provider.rate_calculator.is_holiday(date, holiday_config)
    
    def get_all_current_rates(self) -> Dict[str, Any]:
        """Get all current rates using provider calculator."""
        if not self._tariff_data:
            return {}
        return self.provider.rate_calculator.get_all_current_rates(
            datetime.now(), self._tariff_data
        )
    
    def supports_real_time_rates(self) -> bool:
        """Check if provider supports real-time rates."""
        return self.provider.data_source.supports_real_time_rates()
    
    @property
    def update_interval(self) -> timedelta:
        """Get recommended update interval based on data source."""
        return self.provider.data_source.get_update_interval()
    
    def _get_appropriate_extractor(self, source_config: Dict[str, Any]) -> ProviderDataExtractor:
        """Get the appropriate data extractor based on configuration.
        
        This allows providers to use different extractors for different states or configurations.
        For example, a provider might use APIs in some states and PDFs in others.
        """
        # Check if the provider has a method to get state-specific extractors
        if hasattr(self.provider, 'get_data_extractor_for_state'):
            return self.provider.get_data_extractor_for_state(self.state)
        
        # Otherwise use the default extractor
        return self.provider.data_extractor