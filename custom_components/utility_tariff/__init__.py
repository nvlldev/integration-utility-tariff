"""Generic utility tariff integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_REFRESH_RATES,
    SERVICE_CLEAR_CACHE,
    SERVICE_CALCULATE_BILL,
    SERVICE_RESET_METER,
    ATTR_ENTITY_ID,
    ATTR_RESET_ALL,
)
from .tariff_manager import GenericTariffManager
from .coordinator import DynamicCoordinator, PDFCoordinator
from .providers.registry import initialize_providers, get_available_providers

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Service schemas
CALCULATE_BILL_SCHEMA = vol.Schema({
    vol.Required("kwh_usage"): cv.positive_float,
    vol.Optional("days", default=30): cv.positive_int,
})

RESET_METER_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_RESET_ALL, default=False): cv.boolean,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up utility tariff from a config entry."""
    
    # Initialize providers on first setup
    initialize_providers()
    
    # Get the provider for this config entry
    provider_id = entry.data.get("provider")
    if not provider_id:
        # For backward compatibility with existing Xcel Energy entries
        provider_id = "xcel_energy"
    
    providers = get_available_providers()
    if provider_id not in providers:
        _LOGGER.error("Provider %s not available", provider_id)
        return False
    
    provider = providers[provider_id]
    
    # Extract configuration
    state = entry.data["state"]
    service_type = entry.data["service_type"]
    rate_schedule = entry.options.get("rate_schedule", entry.data.get("rate_schedule", "residential"))
    
    # Validate configuration with provider
    is_valid, error_msg = provider.validate_configuration(state, service_type, rate_schedule)
    if not is_valid:
        _LOGGER.error(
            "Invalid configuration for %s: %s",
            provider.name, error_msg
        )
        return False
    
    # Create generic tariff manager
    tariff_manager = GenericTariffManager(
        hass=hass,
        provider=provider,
        state=state,
        service_type=service_type,
        rate_schedule=rate_schedule,
        options=entry.options
    )
    
    # Create coordinators
    pdf_coordinator = PDFCoordinator(
        hass=hass,
        tariff_manager=tariff_manager._provider_manager,  # Pass the provider manager
        update_frequency=entry.options.get("update_frequency", "weekly")
    )
    
    dynamic_coordinator = DynamicCoordinator(
        hass=hass,
        tariff_manager=tariff_manager,  # Pass the full tariff manager
        pdf_coordinator=pdf_coordinator
    )
    
    # Initialize with fallback data immediately to prevent unavailable states
    await tariff_manager.initialize_with_fallback()
    
    # Trigger initial data load
    await pdf_coordinator.async_request_refresh()
    await dynamic_coordinator.async_request_refresh()
    
    # Get state name for storage
    from .const import ALL_STATES
    state_name = ALL_STATES.get(state, state)
    
    # Store data for other components
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "tariff_manager": tariff_manager,
        "pdf_coordinator": pdf_coordinator,
        "dynamic_coordinator": dynamic_coordinator,
        "provider": provider,
        "state_name": state_name,
    }
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    # Set up services (only once)
    await _async_setup_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entries to new format."""
    version = config_entry.version
    
    if version == 1 or version == 2:
        # Migrate from Xcel-only to multi-provider format
        new_data = dict(config_entry.data)
        
        # Add provider if missing (assume Xcel Energy for old entries)
        if "provider" not in new_data:
            new_data["provider"] = "xcel_energy"
        
        # Update version
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=new_data)
        
        _LOGGER.info("Migrated config entry to version 3 (multi-provider)")
        
    return True


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the integration."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_RATES):
        return
    
    async def handle_refresh_rates(call: ServiceCall) -> None:
        """Handle the refresh_rates service call."""
        entry_id = list(hass.data[DOMAIN].keys())[0]  # Get first entry
        if entry_id in hass.data[DOMAIN]:
            pdf_coordinator = hass.data[DOMAIN][entry_id]["pdf_coordinator"]
            await pdf_coordinator.async_refresh_data()
            _LOGGER.info("Tariff rates refresh requested")
    
    async def handle_clear_cache(call: ServiceCall) -> None:
        """Handle the clear_cache service call."""
        entry_id = list(hass.data[DOMAIN].keys())[0]  # Get first entry
        if entry_id in hass.data[DOMAIN]:
            pdf_coordinator = hass.data[DOMAIN][entry_id]["pdf_coordinator"]
            # Clear the last successful update to force refresh
            pdf_coordinator._last_successful_update = None
            await pdf_coordinator.async_refresh_data()
            _LOGGER.info("Tariff cache cleared and refresh requested")
    
    async def handle_calculate_bill(call: ServiceCall) -> None:
        """Handle the calculate_bill service call."""
        kwh_usage = call.data["kwh_usage"]
        days = call.data["days"]
        
        entry_id = list(hass.data[DOMAIN].keys())[0]  # Get first entry
        if entry_id in hass.data[DOMAIN]:
            tariff_manager = hass.data[DOMAIN][entry_id]["tariff_manager"]
            current_rate = tariff_manager.get_current_rate()
            
            if current_rate:
                # Calculate energy cost
                energy_cost = kwh_usage * current_rate
                
                # Get fixed charges
                all_rates = tariff_manager.get_all_current_rates()
                monthly_charge = all_rates.get("fixed_charges", {}).get("monthly_service", 0)
                
                # Pro-rate fixed charge for the number of days
                daily_charge = monthly_charge / 30
                fixed_cost = daily_charge * days
                
                # Total bill
                total_bill = energy_cost + fixed_cost
                
                hass.bus.async_fire(
                    f"{DOMAIN}_bill_calculated",
                    {
                        "kwh_usage": kwh_usage,
                        "days": days,
                        "energy_cost": round(energy_cost, 2),
                        "fixed_cost": round(fixed_cost, 2),
                        "total_bill": round(total_bill, 2),
                        "rate_per_kwh": current_rate,
                    }
                )
                _LOGGER.info(
                    "Bill calculated: $%.2f (%.1f kWh @ $%.4f/kWh + $%.2f fixed)",
                    total_bill, kwh_usage, current_rate, fixed_cost
                )
    
    async def handle_reset_meter(call: ServiceCall) -> None:
        """Handle the reset_meter service call."""
        entity_ids = call.data.get(ATTR_ENTITY_ID, [])
        reset_all = call.data.get(ATTR_RESET_ALL, False)
        
        # Count of reset meters
        reset_count = 0
        
        # If reset_all or no specific entities provided, reset all utility meters
        if reset_all or not entity_ids:
            # Reset all meters from all config entries
            for entry_id, entry_data in hass.data[DOMAIN].items():
                if "utility_meters" in entry_data:
                    for meter in entry_data["utility_meters"]:
                        await meter.async_reset()
                        _LOGGER.info("Reset utility meter: %s", meter.entity_id)
                        reset_count += 1
            
            if reset_count == 0:
                _LOGGER.warning("No utility meters found to reset")
            else:
                _LOGGER.info("Reset %d utility meters", reset_count)
        else:
            # Reset specific entities
            for entity_id in entity_ids:
                meter_found = False
                
                # Search through all config entries for the meter
                for entry_id, entry_data in hass.data[DOMAIN].items():
                    if "utility_meters" in entry_data:
                        for meter in entry_data["utility_meters"]:
                            if meter.entity_id == entity_id:
                                await meter.async_reset()
                                _LOGGER.info("Reset utility meter: %s", entity_id)
                                meter_found = True
                                reset_count += 1
                                break
                    if meter_found:
                        break
                
                if not meter_found:
                    # Check if it's a utility meter by checking state attributes
                    entity_state = hass.states.get(entity_id)
                    if (entity_state and 
                        entity_state.attributes.get("meter_type") in ["net_consumption", "energy_received", "energy_delivered"]):
                        _LOGGER.warning(
                            "Entity %s is a utility meter but not accessible for reset",
                            entity_id
                        )
                    else:
                        _LOGGER.warning(
                            "Entity %s is not a utility meter or doesn't exist",
                            entity_id
                        )
    
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_RATES, handle_refresh_rates)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_CACHE, handle_clear_cache)
    hass.services.async_register(
        DOMAIN, SERVICE_CALCULATE_BILL, handle_calculate_bill, schema=CALCULATE_BILL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_METER, handle_reset_meter, schema=RESET_METER_SCHEMA
    )