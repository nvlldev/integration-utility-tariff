"""Generic tariff manager that works with any utility provider."""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ERROR_CODES
from .providers import ProviderTariffManager, UtilityProvider

_LOGGER = logging.getLogger(__name__)


class GenericTariffManager:
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
        """Initialize the generic tariff manager."""
        self.hass = hass
        self.provider = provider
        self.state = state
        self.service_type = service_type
        self.rate_schedule = rate_schedule
        self._options = options
        
        # Provider-specific tariff manager
        self._provider_manager = ProviderTariffManager(
            hass, provider, state, service_type, rate_schedule, self._options
        )
        
        # Cache and state management
        self._tariff_data: Dict[str, Any] = {}
        self._last_successful_update: Optional[datetime] = None
        self._rate_cache = {}
        self._last_rate_cache_clear = dt_util.now()
        
        # File paths
        self._cache_dir = Path(hass.config.path("custom_components", DOMAIN, "cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        _LOGGER.info(
            "Initialized %s tariff manager for %s %s %s",
            provider.name, state, service_type, rate_schedule
        )
    
    async def initialize_with_fallback(self) -> None:
        """Initialize with fallback data to prevent unavailable states on startup."""
        try:
            # Try to load from cache first
            cached_data = await self._load_cache()
            if cached_data:
                self._tariff_data = cached_data
                self._provider_manager.tariff_data = cached_data
                _LOGGER.info("Loaded cached tariff data for startup")
                return
        except Exception as e:
            _LOGGER.debug("Could not load cache: %s", e)
        
        # If no cache, use fallback rates immediately
        try:
            fallback_data = self._provider_manager._get_fallback_rates()
            if fallback_data:
                self._tariff_data = fallback_data
                self._tariff_data["data_source"] = "fallback_startup"
                self._provider_manager.tariff_data = fallback_data
                _LOGGER.info("Using fallback rates for startup to prevent unavailable states")
        except Exception as e:
            _LOGGER.warning("Could not load fallback rates: %s", e)
    
    async def async_update_tariffs(self) -> Dict[str, Any]:
        """Update tariff data using provider implementation."""
        try:
            _LOGGER.debug("Starting tariff update for %s", self.provider.name)
            
            # Delegate to provider manager
            result = await self._provider_manager.async_update_tariffs()
            
            if result:
                self._tariff_data = result
                self._last_successful_update = dt_util.now()
                
                # Save to cache
                await self._save_cache(result)
                
                _LOGGER.info(
                    "Successfully updated %s tariff data for %s %s",
                    self.provider.name, self.state, self.service_type
                )
                
                # Clear any existing repair issues
                self._clear_repair_issues()
                
                return result
            else:
                _LOGGER.warning("Provider returned empty tariff data")
                return await self._handle_update_failure("Empty response from provider")
                
        except Exception as err:
            _LOGGER.error("Error updating tariff data: %s", err)
            return await self._handle_update_failure(str(err))
    
    def get_current_rate(self) -> Optional[float]:
        """Get current rate using provider calculator."""
        return self._provider_manager.get_current_rate()
    
    def get_current_tou_period(self) -> str:
        """Get current TOU period using provider calculator."""
        return self._provider_manager.get_current_tou_period()
    
    def is_summer_season(self, time: datetime) -> bool:
        """Check if time is in summer season using provider calculator."""
        return self._provider_manager.is_summer_season(time)
    
    def is_holiday(self, date) -> bool:
        """Check if date is a holiday using provider calculator."""
        return self._provider_manager.is_holiday(date)
    
    def get_all_current_rates(self) -> Dict[str, Any]:
        """Get all current rates using provider calculator."""
        return self._provider_manager.get_all_current_rates()
    
    def _get_fallback_rates(self) -> Dict[str, Any]:
        """Get fallback rates from provider."""
        try:
            return self.provider.data_source.get_fallback_rates(
                self.state, self.service_type
            )
        except Exception as err:
            _LOGGER.warning("Error getting fallback rates: %s", err)
            return {}
    
    async def _handle_update_failure(self, error_message: str) -> Dict[str, Any]:
        """Handle tariff update failure."""
        # Try to load from cache first
        cached_data = await self._load_cache()
        if cached_data:
            _LOGGER.info("Using cached tariff data due to update failure")
            # Mark that we're using cached data but keep original data_source
            cached_data["using_cache"] = True
            cached_data["cache_reason"] = error_message
            self._tariff_data = cached_data
            
            # Create repair issue for failed update
            self._create_repair_issue(
                "pdf_update_failed",
                f"Failed to update {self.provider.name} tariff data: {error_message}. Using cached data."
            )
            
            return cached_data
        
        # Try provider fallback rates
        try:
            fallback_data = self.provider.url_builder.get_fallback_rates(
                self.state, self.service_type
            )
            if fallback_data:
                _LOGGER.info("Using %s fallback rates", self.provider.name)
                self._tariff_data = {
                    **fallback_data,
                    "provider": self.provider.provider_id,
                    "data_source": "fallback",
                    "last_updated": dt_util.now().isoformat(),
                }
                
                # Create repair issue for fallback usage
                self._create_repair_issue(
                    "using_fallback_rates",
                    f"Unable to retrieve current {self.provider.name} tariff data. Using fallback rates. Error: {error_message}"
                )
                
                return self._tariff_data
        except Exception as fallback_err:
            _LOGGER.error("Fallback rates also failed: %s", fallback_err)
        
        # Create repair issue for complete failure
        self._create_repair_issue(
            "no_tariff_data",
            f"Unable to retrieve any {self.provider.name} tariff data. Both live updates and fallback rates failed."
        )
        
        return {}
    
    async def _save_cache(self, data: Dict[str, Any]) -> None:
        """Save tariff data to cache file."""
        try:
            cache_file = self._cache_dir / f"{self.provider.provider_id}_{self.state}_{self.service_type}_{self.rate_schedule}.json"
            
            import json
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(json.dumps(data, indent=2))
                
            _LOGGER.debug("Saved tariff data to cache: %s", cache_file)
        except Exception as err:
            _LOGGER.warning("Failed to save cache: %s", err)
    
    async def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load tariff data from cache file."""
        try:
            cache_file = self._cache_dir / f"{self.provider.provider_id}_{self.state}_{self.service_type}_{self.rate_schedule}.json"
            
            if not cache_file.exists():
                return None
            
            import json
            async with aiofiles.open(cache_file, "r") as f:
                content = await f.read()
                data = json.loads(content)
                
            _LOGGER.debug("Loaded tariff data from cache: %s", cache_file)
            return data
        except Exception as err:
            _LOGGER.warning("Failed to load cache: %s", err)
            return None
    
    def _create_repair_issue(self, issue_id: str, description: str) -> None:
        """Create a repair issue for Home Assistant."""
        try:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.provider.provider_id}_{self.state}_{issue_id}",
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={
                    "provider": self.provider.name,
                    "state": self.state,
                    "error": description,
                },
            )
        except Exception as err:
            _LOGGER.warning("Failed to create repair issue: %s", err)
    
    def _clear_repair_issues(self) -> None:
        """Clear any existing repair issues."""
        try:
            issue_ids = [
                f"{self.provider.provider_id}_{self.state}_pdf_update_failed",
                f"{self.provider.provider_id}_{self.state}_using_fallback_rates",
                f"{self.provider.provider_id}_{self.state}_no_tariff_data",
            ]
            
            for issue_id in issue_ids:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        except Exception as err:
            _LOGGER.debug("No repair issues to clear: %s", err)
    
    @property
    def provider_name(self) -> str:
        """Get provider display name."""
        return self.provider.name
    
    @property
    def provider_short_name(self) -> str:
        """Get provider short name."""
        return self.provider.short_name
    
    @property
    def tariff_data(self) -> Dict[str, Any]:
        """Get current tariff data."""
        return self._tariff_data
    
    @property
    def last_successful_update(self) -> Optional[datetime]:
        """Get last successful update time."""
        return self._last_successful_update
    
    @property
    def options(self) -> Dict[str, Any]:
        """Get configuration options."""
        return self._options


class LegacyTariffManagerAdapter:
    """Adapter to maintain compatibility with existing code."""
    
    def __init__(self, generic_manager: GenericTariffManager):
        """Initialize adapter with generic manager."""
        self._manager = generic_manager
        
    # Delegate all calls to the generic manager
    def __getattr__(self, name):
        return getattr(self._manager, name)
    
    # Legacy property names for backward compatibility
    @property
    def _tariff_data(self):
        return self._manager.tariff_data
    
    @_tariff_data.setter
    def _tariff_data(self, value):
        self._manager._tariff_data = value