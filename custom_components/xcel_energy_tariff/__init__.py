"""The Xcel Energy Tariff integration v2."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .coordinator import XcelDynamicCoordinator, XcelPDFCoordinator
from .tariff_manager import XcelTariffManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service schemas
SERVICE_REFRESH_RATES = "refresh_rates"
SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_CALCULATE_BILL = "calculate_bill"

CALCULATE_BILL_SCHEMA = vol.Schema({
    vol.Required("kwh_usage"): cv.positive_float,
    vol.Optional("days", default=30): cv.positive_int,
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Xcel Energy Tariff integration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register services
    async def handle_refresh_rates(call: ServiceCall) -> None:
        """Handle refresh rates service call."""
        for entry_id, data in hass.data[DOMAIN].items():
            if entry_id == "services":
                continue
            pdf_coordinator = data.get("pdf_coordinator")
            if pdf_coordinator:
                await pdf_coordinator.async_refresh_data()
                _LOGGER.info("Refreshed rates for %s", entry_id)
    
    async def handle_clear_cache(call: ServiceCall) -> None:
        """Handle clear cache service call."""
        for entry_id, data in hass.data[DOMAIN].items():
            if entry_id == "services":
                continue
            tariff_manager = data.get("tariff_manager")
            if tariff_manager:
                tariff_manager.clear_cache()
                _LOGGER.info("Cleared cache for %s", entry_id)
    
    async def handle_calculate_bill(call: ServiceCall) -> dict[str, Any]:
        """Handle calculate bill service call."""
        kwh_usage = call.data["kwh_usage"]
        days = call.data["days"]
        
        results = {}
        for entry_id, data in hass.data[DOMAIN].items():
            if entry_id == "services":
                continue
                
            tariff_manager = data.get("tariff_manager")
            if not tariff_manager:
                continue
                
            # Calculate costs
            all_rates = tariff_manager.get_all_current_rates()
            base_rate = all_rates.get("base_rate", 0)
            fixed_charges = all_rates.get("fixed_charges", {})
            additional_charges = all_rates.get("total_additional", 0)
            
            # Calculate energy cost
            energy_cost = kwh_usage * (base_rate + additional_charges)
            
            # Pro-rate fixed charges
            monthly_fixed = fixed_charges.get("monthly_service", 0)
            fixed_cost = (monthly_fixed / 30) * days
            
            total_cost = energy_cost + fixed_cost
            
            results[entry_id] = {
                "energy_cost": round(energy_cost, 2),
                "fixed_cost": round(fixed_cost, 2),
                "total_cost": round(total_cost, 2),
                "average_rate": round(total_cost / kwh_usage, 4) if kwh_usage > 0 else 0,
            }
            
        return results
    
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_RATES, handle_refresh_rates)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_CACHE, handle_clear_cache)
    hass.services.async_register(
        DOMAIN, 
        SERVICE_CALCULATE_BILL, 
        handle_calculate_bill,
        schema=CALCULATE_BILL_SCHEMA,
    )
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xcel Energy Tariff from a config entry."""
    # Get options with defaults
    options = {**entry.data, **entry.options}
    
    # Create tariff manager
    tariff_manager = XcelTariffManager(
        hass,
        entry.data["state"],
        entry.data["service_type"],
        options.get("rate_schedule", entry.data.get("rate_schedule", "residential")),
        options,
    )
    
    # Initialize tariff manager asynchronously
    await tariff_manager.async_initialize()
    
    # Create coordinators
    pdf_coordinator = XcelPDFCoordinator(
        hass,
        tariff_manager,
        options.get("update_frequency", "weekly"),
    )
    
    dynamic_coordinator = XcelDynamicCoordinator(
        hass,
        tariff_manager,
        pdf_coordinator,
    )
    
    # Initial data fetch
    await pdf_coordinator.async_config_entry_first_refresh()
    await dynamic_coordinator.async_config_entry_first_refresh()
    
    # Store references
    hass.data[DOMAIN][entry.entry_id] = {
        "pdf_coordinator": pdf_coordinator,
        "dynamic_coordinator": dynamic_coordinator,
        "tariff_manager": tariff_manager,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Update tariff manager with new options
    data = hass.data[DOMAIN][entry.entry_id]
    tariff_manager = data["tariff_manager"]
    
    # Merge options
    options = {**entry.data, **entry.options}
    tariff_manager.update_options(options)
    
    # Update PDF coordinator frequency if changed
    pdf_coordinator = data["pdf_coordinator"]
    new_frequency = options.get("update_frequency", "weekly")
    if new_frequency == "daily":
        pdf_coordinator.update_interval = timedelta(hours=24)
    else:
        pdf_coordinator.update_interval = timedelta(days=7)
    
    # Force refresh coordinators
    await pdf_coordinator.async_request_refresh()
    await data["dynamic_coordinator"].async_request_refresh()