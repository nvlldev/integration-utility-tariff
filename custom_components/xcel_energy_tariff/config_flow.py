"""Config flow for Xcel Energy Tariff integration v2."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    STATES,
    SERVICE_TYPES,
    SERVICE_TYPE_ELECTRIC,
    SERVICE_TYPE_GAS,
    RATE_SCHEDULES,
)

_LOGGER = logging.getLogger(__name__)

def get_rate_options(service_type: str) -> dict[str, str]:
    """Get rate schedule options based on service type."""
    if service_type == SERVICE_TYPE_ELECTRIC:
        return {
            "residential": "Residential",
            "residential_tou": "Residential Time-of-Use",
            "residential_ev": "Residential EV",
            "commercial": "Commercial",
            "commercial_tou": "Commercial Time-of-Use",
        }
    else:
        return {
            "residential_gas": "Residential Gas",
            "commercial_gas": "Commercial Gas",
        }


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Check if state supports the selected service type
    if data["service_type"] == SERVICE_TYPE_GAS and data["state"] not in ["CO", "MN", "WI", "MI"]:
        raise ValueError("gas_not_available")
    
    return {"title": f"Xcel Energy {STATES[data['state']]} {data['service_type'].title()}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xcel Energy Tariff."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - basic configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Check if just changing service type (no setup_type means form reload)
            if "setup_type" not in user_input:
                # Form is being reloaded due to service type change
                # Preserve the input and show form again with updated rate options
                pass
            else:
                try:
                    info = await validate_input(self.hass, user_input)
                except ValueError as exc:
                    errors["base"] = str(exc)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    # Store basic data
                    self._data = user_input
                    self._data["title"] = info["title"]
                    self._data["rate_schedule"] = user_input["rate_schedule"]
                    
                    # Check setup type
                    setup_type = user_input.get("setup_type", "quick")
                    if setup_type == "quick":
                        # Quick setup - use provided values plus defaults
                        self._options = {
                            "rate_schedule": user_input["rate_schedule"],
                            "update_frequency": "weekly",
                            "summer_months": "6,7,8,9",
                            "enable_cost_sensors": True,
                            "consumption_entity": user_input.get("consumption_entity", "none"),
                            "average_daily_usage": user_input.get("average_daily_usage", 30.0),
                            "include_additional_charges": True,
                        }
                        
                        # Add TOU defaults if TOU rate selected
                        if "tou" in user_input["rate_schedule"]:
                            self._options.update({
                                "peak_start": "15:00",
                                "peak_end": "19:00",
                                "shoulder_start": "13:00",
                                "shoulder_end": "15:00",
                                "custom_holidays": "",
                            })
                        
                        return self.async_create_entry(
                            title=self._data["title"],
                            data=self._data,
                            options=self._options
                        )
                    else:
                        # Custom setup - store rate schedule in options
                        self._options = {"rate_schedule": user_input["rate_schedule"]}
                        
                        # Go to TOU config if needed, otherwise additional options
                        if "tou" in user_input["rate_schedule"]:
                            return await self.async_step_tou_config()
                        else:
                            return await self.async_step_additional_options()

        # Build dynamic schema based on selected service type
        service_type = user_input.get("service_type", SERVICE_TYPE_ELECTRIC) if user_input else SERVICE_TYPE_ELECTRIC
        rate_options = get_rate_options(service_type)
        default_rate = user_input.get("rate_schedule", "residential" if service_type == SERVICE_TYPE_ELECTRIC else "residential_gas") if user_input else "residential"
        
        # Get consumption entities
        entities = self._get_consumption_entities()
        entity_options = {"none": "Manual Entry (Average Daily Usage)"}
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state:
                name = state.attributes.get("friendly_name", entity_id)
                entity_options[entity_id] = name

        # Show/hide average daily usage based on consumption entity selection
        consumption_entity = user_input.get("consumption_entity", "none") if user_input else "none"
        
        schema_dict = {
            vol.Required("state", default=user_input.get("state") if user_input else None): vol.In(list(STATES.keys())),
            vol.Required("service_type", default=service_type): vol.In(list(SERVICE_TYPES.keys())),
            vol.Required("rate_schedule", default=default_rate): vol.In(rate_options),
            vol.Optional("consumption_entity", default=consumption_entity): vol.In(entity_options),
        }
        
        # Only show average daily usage if manual entry selected
        if consumption_entity == "none":
            schema_dict[vol.Optional("average_daily_usage", default=user_input.get("average_daily_usage", 30.0) if user_input else 30.0)] = cv.positive_float
            
        schema_dict[vol.Required("setup_type", default="quick")] = vol.In({
            "quick": "Quick Setup (Recommended)",
            "custom": "Custom Setup"
        })

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user", 
            data_schema=schema, 
            errors=errors,
            description_placeholders={
                "info": "The average daily usage field is only needed if you select Manual Entry for consumption."
            }
        )

    def _get_consumption_entities(self) -> list[str]:
        """Get list of potential consumption entities."""
        entities = []
        
        # Check all sensor states
        for state in self.hass.states.async_all("sensor"):
            if state.attributes.get("unit_of_measurement") in ["kWh", "Wh"]:
                entities.append(state.entity_id)
        
        # Also check entity registry
        entity_registry = er.async_get(self.hass)
        for entity_id, entity in entity_registry.entities.items():
            if entity.domain == "sensor" and entity.device_class in ["energy", "power"]:
                if entity_id not in entities:
                    state = self.hass.states.get(entity_id)
                    if state and state.attributes.get("unit_of_measurement") in ["kWh", "Wh"]:
                        entities.append(entity_id)
        
        # Sort for better display
        entities.sort()
        return entities

    async def async_step_rate_plan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle rate plan selection."""
        if user_input is not None:
            self._data["rate_schedule"] = user_input["rate_schedule"]
            self._options["rate_schedule"] = user_input["rate_schedule"]
            self._options["update_frequency"] = user_input.get("update_frequency", "weekly")
            
            # Check if user wants to configure more options
            if not user_input.get("configure_more", True):
                # Use defaults for everything else
                self._options.update({
                    "summer_months": "6,7,8,9",
                    "enable_cost_sensors": True,
                    "consumption_entity": "none",
                    "average_daily_usage": 30.0,
                    "include_additional_charges": True,
                })
                return self.async_create_entry(
                    title=self._data["title"],
                    data=self._data,
                    options=self._options
                )
            
            # If TOU rate, go to TOU configuration
            if "tou" in user_input["rate_schedule"]:
                return await self.async_step_tou_config()
            else:
                return await self.async_step_additional_options()

        # Build rate options based on service type
        rate_options = get_rate_options(self._data["service_type"])
        default_rate = self._data.get("rate_schedule", "residential" if self._data["service_type"] == SERVICE_TYPE_ELECTRIC else "residential_gas")

        schema = vol.Schema(
            {
                vol.Required("rate_schedule", default=default_rate): vol.In(rate_options),
                vol.Optional("update_frequency", default="weekly"): vol.In({
                    "daily": "Daily", 
                    "weekly": "Weekly"
                }),
                vol.Optional("configure_more", default=True): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="rate_plan", 
            data_schema=schema,
            description_placeholders={"service_type": self._data["service_type"].title()}
        )

    async def async_step_tou_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle TOU configuration."""
        if user_input is not None:
            # Remove the skip_additional flag before updating options
            skip_additional = user_input.pop("skip_additional", False)
            self._options.update(user_input)
            
            if skip_additional:
                # Use defaults for remaining options
                self._options.update({
                    "summer_months": "6,7,8,9",
                    "enable_cost_sensors": True,
                    "consumption_entity": "none",
                    "average_daily_usage": 30.0,
                    "include_additional_charges": True,
                })
                return self.async_create_entry(
                    title=self._data["title"],
                    data=self._data,
                    options=self._options
                )
            
            return await self.async_step_additional_options()

        schema = vol.Schema(
            {
                vol.Optional("peak_start", default="15:00"): cv.string,
                vol.Optional("peak_end", default="19:00"): cv.string,
                vol.Optional("shoulder_start", default="13:00"): cv.string,
                vol.Optional("shoulder_end", default="15:00"): cv.string,
                vol.Optional("custom_holidays"): cv.string,
                vol.Optional("skip_additional", default=False): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="tou_config",
            data_schema=schema,
            description_placeholders={
                "info": "Configure Time-of-Use schedule (optional). Times are in 24-hour format (HH:MM)."
            }
        )

    async def async_step_additional_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle additional options."""
        if user_input is not None:
            self._options.update(user_input)
            
            # Create the config entry with both data and options
            return self.async_create_entry(
                title=self._data["title"],
                data=self._data,
                options=self._options
            )

        # Get list of sensor entities that could be power consumption
        entities = self._get_consumption_entities()
        
        # Add "None" option for manual entry
        entity_options = {"none": "Manual Entry (Average Daily Usage)"}
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state:
                name = state.attributes.get("friendly_name", entity_id)
                entity_options[entity_id] = name

        schema = vol.Schema(
            {
                vol.Optional("summer_months", default="6,7,8,9"): cv.string,
                vol.Optional("enable_cost_sensors", default=True): cv.boolean,
                vol.Optional("consumption_entity", default="none"): vol.In(entity_options),
                vol.Optional("average_daily_usage", default=30.0): cv.positive_float,
                vol.Optional("include_additional_charges", default=True): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="additional_options",
            data_schema=schema,
            description_placeholders={
                "info": "Configure additional options for rate calculations and sensors."
            }
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Xcel Energy Tariff."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - simplified view."""
        if user_input is not None:
            if user_input.get("show_advanced", False):
                return await self.async_step_advanced()
            
            # Remove the flag before saving
            user_input.pop("show_advanced", None)
            
            # Merge with existing options to preserve advanced settings
            updated_options = dict(self.config_entry.options)
            updated_options.update(user_input)
            
            return self.async_create_entry(title="", data=updated_options)

        # Get current values
        current_schedule = self.config_entry.options.get(
            "rate_schedule", 
            self.config_entry.data.get("rate_schedule", "residential")
        )
        
        # Build rate schedule options based on service type
        service_type = self.config_entry.data["service_type"]
        rate_options = get_rate_options(service_type)

        # Get list of sensor entities that could be power consumption
        entities = self._get_consumption_entities()
        
        # Add "None" option for manual entry
        entity_options = {"none": "Manual Entry (Average Daily Usage)"}
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state:
                name = state.attributes.get("friendly_name", entity_id)
                entity_options[entity_id] = name

        # Get current consumption entity
        current_consumption_entity = self.config_entry.options.get("consumption_entity", "none")
        if current_consumption_entity not in entity_options:
            current_consumption_entity = "none"

        # Simplified schema - only most important options
        schema = vol.Schema(
            {
                vol.Required("rate_schedule", default=current_schedule): vol.In(rate_options),
                vol.Optional(
                    "consumption_entity",
                    default=current_consumption_entity
                ): vol.In(entity_options),
                vol.Optional(
                    "average_daily_usage",
                    default=self.config_entry.options.get("average_daily_usage", 30.0)
                ): cv.positive_float,
                vol.Optional(
                    "enable_cost_sensors",
                    default=self.config_entry.options.get("enable_cost_sensors", True)
                ): cv.boolean,
                vol.Optional("show_advanced", default=False): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init", 
            data_schema=schema,
            description_placeholders={
                "info": "Configure basic options. Enable 'Show Advanced Options' for more settings."
            }
        )
    
    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced options."""
        if user_input is not None:
            # Merge with existing options
            updated_options = dict(self.config_entry.options)
            updated_options.update(user_input)
            
            return self.async_create_entry(title="", data=updated_options)

        # Get current values
        current_schedule = self.config_entry.options.get(
            "rate_schedule", 
            self.config_entry.data.get("rate_schedule", "residential")
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "update_frequency",
                    default=self.config_entry.options.get("update_frequency", "weekly")
                ): vol.In({"daily": "Daily", "weekly": "Weekly"}),
                vol.Optional(
                    "summer_months",
                    default=self.config_entry.options.get("summer_months", "6,7,8,9")
                ): cv.string,
                vol.Optional(
                    "include_additional_charges",
                    default=self.config_entry.options.get("include_additional_charges", True)
                ): cv.boolean,
            }
        )

        # Add TOU-specific options if applicable
        if "tou" in current_schedule:
            schema = schema.extend({
                vol.Optional(
                    "peak_start",
                    default=self.config_entry.options.get("peak_start", "15:00")
                ): cv.string,
                vol.Optional(
                    "peak_end", 
                    default=self.config_entry.options.get("peak_end", "19:00")
                ): cv.string,
                vol.Optional(
                    "shoulder_start",
                    default=self.config_entry.options.get("shoulder_start", "13:00")
                ): cv.string,
                vol.Optional(
                    "shoulder_end",
                    default=self.config_entry.options.get("shoulder_end", "15:00")
                ): cv.string,
                vol.Optional(
                    "custom_holidays",
                    default=self.config_entry.options.get("custom_holidays", "")
                ): cv.string,
            })

        return self.async_show_form(
            step_id="advanced", 
            data_schema=schema,
            description_placeholders={
                "info": "Configure advanced options."
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""