"""Repairs support for Xcel Energy Tariff integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class XcelEnergyTariffRepairFlow(RepairsFlow):
    """Handler for Xcel Energy Tariff repair flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry
        self._pdf_url: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_pdf_error()

    async def async_step_pdf_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle PDF parsing error repair."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "retry":
                # Try to reload the integration
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_create_entry(data={})
                
            elif action == "manual":
                return await self.async_step_manual_rates()
                
            elif action == "fallback":
                # Update options to force fallback rates
                options = dict(self._entry.options)
                options["force_fallback"] = True
                self.hass.config_entries.async_update_entry(
                    self._entry, options=options
                )
                return self.async_create_entry(data={})
                
            elif action == "alternative_url":
                return await self.async_step_alternative_url()

        return self.async_show_form(
            step_id="pdf_error",
            data_schema=vol.Schema({
                vol.Required("action", default="retry"): vol.In({
                    "retry": "Retry PDF Download",
                    "manual": "Enter Rates Manually",
                    "fallback": "Use Fallback Rates",
                    "alternative_url": "Try Alternative PDF URL",
                }),
            }),
            description_placeholders={
                "error_details": "The PDF tariff sheet could not be downloaded or parsed.",
            }
        )

    async def async_step_manual_rates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual rate entry."""
        errors = {}
        
        if user_input is not None:
            # Validate and save manual rates
            try:
                # Update options with manual rates
                options = dict(self._entry.options)
                options["manual_rates"] = {
                    "base_rate": user_input["base_rate"],
                    "fixed_charge": user_input["fixed_charge"],
                    "peak_rate": user_input.get("peak_rate"),
                    "off_peak_rate": user_input.get("off_peak_rate"),
                }
                options["use_manual_rates"] = True
                
                self.hass.config_entries.async_update_entry(
                    self._entry, options=options
                )
                
                # Reload the integration
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                
                return self.async_create_entry(data={})
                
            except Exception as e:
                _LOGGER.error("Error saving manual rates: %s", e)
                errors["base"] = "save_failed"

        # Show form based on rate type
        is_tou = "tou" in self._entry.options.get("rate_schedule", "")
        
        if is_tou:
            schema = vol.Schema({
                vol.Required("base_rate", default=0.10): vol.Coerce(float),
                vol.Required("peak_rate", default=0.20): vol.Coerce(float),
                vol.Required("off_peak_rate", default=0.08): vol.Coerce(float),
                vol.Optional("shoulder_rate", default=0.12): vol.Coerce(float),
                vol.Required("fixed_charge", default=10.0): vol.Coerce(float),
            })
        else:
            schema = vol.Schema({
                vol.Required("base_rate", default=0.10): vol.Coerce(float),
                vol.Required("fixed_charge", default=10.0): vol.Coerce(float),
            })

        return self.async_show_form(
            step_id="manual_rates",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "rate_type": "Time-of-Use" if is_tou else "Standard",
                "unit": "$/kWh for rates, $ for monthly charge",
            }
        )

    async def async_step_alternative_url(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle alternative PDF URL entry."""
        errors = {}
        
        if user_input is not None:
            url = user_input.get("pdf_url", "").strip()
            
            if url:
                # Update options with alternative URL
                options = dict(self._entry.options)
                options["alternative_pdf_url"] = url
                
                self.hass.config_entries.async_update_entry(
                    self._entry, options=options
                )
                
                # Reload to try new URL
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                
                return self.async_create_entry(data={})
            else:
                errors["pdf_url"] = "invalid_url"

        # Get current state for example URL
        state = self._entry.data.get("state", "CO")
        service = self._entry.data.get("service_type", "electric")
        example_url = f"https://www.xcelenergy.com/staticfiles/{state}-{service}-tariff.pdf"

        return self.async_show_form(
            step_id="alternative_url",
            data_schema=vol.Schema({
                vol.Required("pdf_url"): str,
            }),
            errors=errors,
            description_placeholders={
                "example_url": example_url,
                "info": "Enter a direct URL to the tariff PDF document.",
            }
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow to handle a repair issue."""
    entry_id = data["entry_id"] if data else None
    
    if not entry_id:
        # Can't repair without knowing which config entry
        return None
        
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        return None
        
    return XcelEnergyTariffRepairFlow(entry)


def async_create_repair_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    error_type: str = "pdf_error",
    error_details: str | None = None,
) -> None:
    """Create a repair issue for the integration."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{error_type}_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=error_type,
        translation_placeholders={
            "name": entry.title,
            "error": error_details or "Unknown error",
        },
        data={"entry_id": entry.entry_id},
    )