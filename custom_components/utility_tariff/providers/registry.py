"""Provider registry and initialization."""

from . import ProviderRegistry
from .xcel_energy import XcelEnergyProvider


def initialize_providers():
    """Initialize and register all available providers."""
    # Register Xcel Energy provider
    xcel_provider = XcelEnergyProvider()
    ProviderRegistry.register_provider(xcel_provider)
    
    # Future providers would be registered here:
    # pge_provider = PGEProvider()
    # ProviderRegistry.register_provider(pge_provider)
    
    # coned_provider = ConEdProvider()
    # ProviderRegistry.register_provider(coned_provider)


def get_available_providers():
    """Get all available providers."""
    return ProviderRegistry.get_all_providers()


def get_provider_for_config(state: str, service_type: str):
    """Get the best provider for a given state and service type."""
    providers = ProviderRegistry.get_providers_for_state(state, service_type)
    
    # For now, return the first available provider
    # In the future, could implement logic to choose the best provider
    # or allow user selection when multiple providers serve the same area
    if providers:
        return providers[0]
    
    return None


def get_provider_choices_for_state(state: str, service_type: str):
    """Get provider choices for config flow."""
    providers = ProviderRegistry.get_providers_for_state(state, service_type)
    
    return {
        provider.provider_id: provider.name
        for provider in providers
    }