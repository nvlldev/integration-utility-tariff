"""Improved config flow for utility tariff integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    ALL_STATES,
    SERVICE_TYPES,
    SERVICE_TYPE_ELECTRIC,
    SERVICE_TYPE_GAS,
    SERVICE_TYPE_WATER,
    CONF_PROVIDER,
    CONF_STATE,
    CONF_SERVICE_TYPE,
    CONF_RATE_SCHEDULE,
)
from .providers.registry import (
    initialize_providers,
    get_available_providers,
)

_LOGGER = logging.getLogger(__name__)

# Extended service types including water
EXTENDED_SERVICE_TYPES = {
    **SERVICE_TYPES,
    SERVICE_TYPE_WATER: "Water",
}


class GenericUtilityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for utility tariff integration."""

    VERSION = 3
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._available_providers: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Select Provider."""
        errors: dict[str, str] = {}
        
        # Initialize providers
        initialize_providers()
        self._available_providers = get_available_providers()
        
        if user_input is not None:
            self._data["provider"] = user_input["provider"]
            return await self.async_step_service_type()
        
        # Build provider dropdown
        provider_choices = {
            p.provider_id: p.name 
            for p in self._available_providers.values()
        }
        
        if not provider_choices:
            provider_choices = {"none": "No providers available"}
        
        schema = vol.Schema({
            vol.Required("provider"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": name, "value": provider_id}
                        for provider_id, name in provider_choices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "title": "Select Your Utility Provider",
                "description": "Choose your electricity or gas provider from the list.",
            }
        )

    async def async_step_service_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Select Service Type."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            if user_input["service_type"] == SERVICE_TYPE_WATER:
                # Show coming soon message for water
                return self.async_abort(
                    reason="water_coming_soon",
                    description_placeholders={
                        "message": "Water service support is coming soon! Please check back in a future update."
                    }
                )
            
            self._data["service_type"] = user_input["service_type"]
            
            # Get provider and check if it supports this service type
            provider = self._available_providers[self._data["provider"]]
            if user_input["service_type"] not in provider.supported_states:
                return self.async_abort(
                    reason="service_not_supported",
                    description_placeholders={
                        "provider": provider.name,
                        "service": EXTENDED_SERVICE_TYPES[user_input["service_type"]]
                    }
                )
            
            return await self.async_step_state()
        
        # Get selected provider
        provider = self._available_providers[self._data["provider"]]
        
        # Build service type choices
        service_choices = {}
        for service_key, service_name in EXTENDED_SERVICE_TYPES.items():
            if service_key in provider.supported_states:
                service_choices[service_key] = service_name
            elif service_key == SERVICE_TYPE_WATER:
                service_choices[service_key] = f"{service_name} (Coming Soon)"
        
        schema = vol.Schema({
            vol.Required("service_type", default=SERVICE_TYPE_ELECTRIC): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": name, "value": service_id}
                        for service_id, name in service_choices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        
        return self.async_show_form(
            step_id="service_type",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "provider": provider.name,
                "description": "Select the type of utility service.",
            }
        )

    async def async_step_state(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Select State."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data["state"] = user_input["state"]
            return await self.async_step_rate_schedule()
        
        # Get provider and service type
        provider = self._available_providers[self._data["provider"]]
        service_type = self._data["service_type"]
        
        # Get supported states for this service
        supported_states = provider.supported_states.get(service_type, [])
        state_choices = {
            code: name 
            for code, name in ALL_STATES.items() 
            if code in supported_states
        }
        
        if not state_choices:
            return self.async_abort(reason="no_states_available")
        
        # If only one state, auto-select it
        if len(state_choices) == 1:
            self._data["state"] = list(state_choices.keys())[0]
            return await self.async_step_rate_schedule()
        
        schema = vol.Schema({
            vol.Required("state"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": name, "value": state_code}
                        for state_code, name in state_choices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
        })
        
        return self.async_show_form(
            step_id="state",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "provider": provider.name,
                "service": EXTENDED_SERVICE_TYPES[service_type],
                "description": "Select your state or region.",
            }
        )

    async def async_step_rate_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Select Rate Schedule."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data["rate_schedule"] = user_input["rate_schedule"]
            self._options["rate_schedule"] = user_input["rate_schedule"]
            return await self.async_step_entities()
        
        # Get provider info
        provider = self._available_providers[self._data["provider"]]
        service_type = self._data["service_type"]
        
        # Get rate schedules
        schedules = provider.supported_rate_schedules.get(service_type, [])
        rate_choices = {
            schedule: self._format_rate_schedule_name(schedule)
            for schedule in schedules
        }
        
        if not rate_choices:
            rate_choices = {"residential": "Residential"}
        
        schema = vol.Schema({
            vol.Required("rate_schedule", default="residential"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": name, "value": schedule}
                        for schedule, name in rate_choices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        
        return self.async_show_form(
            step_id="rate_schedule",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "provider": provider.name,
                "state": ALL_STATES[self._data["state"]],
                "service": EXTENDED_SERVICE_TYPES[service_type],
                "description": "Select your rate plan. Check your utility bill if unsure.",
            }
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 5: Choose energy tracking method."""
        return self.async_show_menu(
            step_id="entities",
            menu_options=["entity_tracking", "manual_tracking", "no_tracking"],
            description_placeholders={
                "title": "Energy Tracking Configuration",
                "description": "Choose how you want to track your energy usage.",
            }
        )

    async def async_step_no_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """No energy tracking - finish setup with defaults."""
        self._options.update({
            "consumption_entity": "none",
            "return_entity": "none",
            "average_daily_usage": 30.0,
        })
        return await self.async_step_finish_or_advanced()

    async def async_step_manual_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual energy tracking - enter average usage."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            daily_usage = user_input.get("average_daily_usage")
            
            # Validate the input
            if daily_usage is None:
                errors["average_daily_usage"] = "daily_usage_required"
            elif daily_usage <= 0:
                errors["average_daily_usage"] = "daily_usage_positive"
            elif daily_usage < 5:
                errors["average_daily_usage"] = "daily_usage_too_low"
            elif daily_usage > 200:
                errors["average_daily_usage"] = "daily_usage_too_high"
            else:
                # Valid input - store manual tracking settings
                self._options.update({
                    "consumption_entity": "none",
                    "return_entity": "none", 
                    "average_daily_usage": float(daily_usage),
                })
                return await self.async_step_finish_or_advanced()
        
        # Get suggested usage based on service type
        service_type = self._data.get("service_type", "electric")
        if service_type == "electric":
            default_usage = 30.0
            usage_range = "20-50 kWh"
            examples = "Small apartment: 15-25 kWh, Average home: 25-40 kWh, Large home: 40-80 kWh"
        else:  # gas
            default_usage = 50.0  # Gas usage is typically higher in therms/day equivalent
            usage_range = "30-100 kWh equivalent"
            examples = "Small home: 20-40 kWh equiv, Average home: 40-70 kWh equiv, Large home: 70-150 kWh equiv"
        
        schema = vol.Schema({
            vol.Required("average_daily_usage", default=default_usage): vol.All(
                cv.positive_float,
                vol.Range(min=5.0, max=200.0)
            ),
        })
        
        return self.async_show_form(
            step_id="manual_tracking",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "service_type": self._data.get("service_type", "electric").title(),
                "usage_range": usage_range,
                "examples": examples,
                "tip": "Find this on your utility bill under 'Usage' or 'Consumption'. Look for kWh (kilowatt-hours) per day or month.",
            }
        )

    async def async_step_entity_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Entity-based tracking - select existing sensors."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Store entity selections
            self._options.update({
                "consumption_entity": user_input.get("consumption_entity", "none"),
                "return_entity": user_input.get("return_entity", "none"),
                "average_daily_usage": 30.0,  # Default for when entity is unavailable
            })
            return await self.async_step_finish_or_advanced()
        
        # Get available entities
        entities = self._get_energy_entities()
        
        if not entities:
            # No energy entities found, redirect to manual tracking
            return self.async_abort(
                reason="no_energy_entities",
                description_placeholders={
                    "message": "No energy sensors found. Please use manual tracking instead."
                }
            )
        
        consumption_choices = [{"label": "None - Skip consumption tracking", "value": "none"}]
        return_choices = [{"label": "None - No solar/grid export", "value": "none"}]
        
        for entity_id, name in entities.items():
            consumption_choices.append({"label": name, "value": entity_id})
            return_choices.append({"label": name, "value": entity_id})
        
        schema = vol.Schema({
            vol.Required("consumption_entity", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=consumption_choices,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("return_entity", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=return_choices,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        
        return self.async_show_form(
            step_id="entity_tracking",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "description": "Select sensors that track your energy usage. The consumption sensor should measure total energy used.",
                "tip": "Return entity is only needed if you have solar panels or other grid export.",
            }
        )

    async def async_step_finish_or_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to choose between finishing setup or continuing to advanced options."""
        return self.async_show_menu(
            step_id="finish_or_advanced",
            menu_options=["finish_setup", "advanced_options"],
            description_placeholders={
                "title": "Setup Options",
                "description": "Choose whether to finish with default settings or configure advanced options.",
            }
        )

    async def async_step_finish_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish setup with default options."""
        self._apply_default_options()
        return self._create_entry()

    async def async_step_advanced_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 6: Advanced Options."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._options.update(user_input)
            return self._create_entry()
        
        # Different schema based on whether it's a TOU rate
        is_tou = "tou" in self._data.get("rate_schedule", "").lower()
        
        schema_dict = {
            vol.Optional("update_frequency", default="daily"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": "Hourly", "value": "hourly"},
                        {"label": "Daily", "value": "daily"},
                        {"label": "Weekly", "value": "weekly"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("enable_cost_sensors", default=True): cv.boolean,
            vol.Optional("include_additional_charges", default=True): cv.boolean,
        }
        
        # Add TOU options if applicable
        if is_tou:
            schema_dict.update({
                vol.Optional("peak_start", default="15:00"): cv.string,
                vol.Optional("peak_end", default="19:00"): cv.string,
                vol.Optional("shoulder_start", default="13:00"): cv.string,
                vol.Optional("shoulder_end", default="15:00"): cv.string,
                vol.Optional("custom_holidays", default=""): cv.string,
            })
        
        # Add seasonal options
        schema_dict.update({
            vol.Optional("summer_months", default="6,7,8,9"): cv.string,
        })
        
        schema = vol.Schema(schema_dict)
        
        return self.async_show_form(
            step_id="advanced_options",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "description": "Configure advanced options. You can change these later in the integration options.",
                "tou_note": "Time-of-Use schedules use 24-hour format (e.g., 15:00 for 3 PM)." if is_tou else "",
            }
        )

    def _format_rate_schedule_name(self, schedule: str) -> str:
        """Format rate schedule name for display."""
        # Handle specific schedule names
        schedule_names = {
            "residential": "Residential",
            "residential_tou": "Residential Time-of-Use",
            "residential_ev": "Residential Electric Vehicle",
            "commercial": "Commercial",
            "commercial_tou": "Commercial Time-of-Use",
            "commercial_demand": "Commercial Demand",
            "residential_gas": "Residential Gas",
            "commercial_gas": "Commercial Gas",
        }
        
        # Return known schedule name or format as title case
        if schedule.lower() in schedule_names:
            return schedule_names[schedule.lower()]
        
        # Default formatting for unknown schedules
        return schedule.replace("_", " ").title()

    def _get_energy_entities(self) -> dict[str, str]:
        """Get available energy entities."""
        entities = {}
        
        # Get all sensor entities with energy measurement
        for state in self.hass.states.async_all("sensor"):
            if state.attributes.get("unit_of_measurement") in ["kWh", "Wh", "MWh"]:
                friendly_name = state.attributes.get("friendly_name", state.entity_id)
                # Add unit to make it clear
                unit = state.attributes.get("unit_of_measurement", "")
                entities[state.entity_id] = f"{friendly_name} ({unit})"
        
        # Sort by friendly name
        return dict(sorted(entities.items(), key=lambda x: x[1]))

    def _apply_default_options(self) -> None:
        """Apply default options for quick setup."""
        defaults = {
            "update_frequency": "daily",
            "enable_cost_sensors": True,
            "include_additional_charges": True,
            "summer_months": "6,7,8,9",
        }
        
        # Add TOU defaults if applicable
        if "tou" in self._data.get("rate_schedule", "").lower():
            defaults.update({
                "peak_start": "15:00",
                "peak_end": "19:00",
                "shoulder_start": "13:00",
                "shoulder_end": "15:00",
                "custom_holidays": "",
            })
        
        # Only apply defaults that aren't already set
        for key, value in defaults.items():
            if key not in self._options:
                self._options[key] = value

    def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        # Build title
        provider = self._available_providers[self._data["provider"]]
        state = ALL_STATES[self._data["state"]]
        service = EXTENDED_SERVICE_TYPES[self._data["service_type"]]
        
        title = f"{provider.name} {state} {service}"
        
        return self.async_create_entry(
            title=title,
            data=self._data,
            options=self._options,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        # Get current values
        is_tou = "tou" in self.config_entry.options.get("rate_schedule", "").lower()
        
        # Get available entities for dropdowns
        entities = self._get_energy_entities()
        consumption_choices = [{"label": "Manual Entry (Use Average)", "value": "none"}]
        return_choices = [{"label": "No Solar/Grid Export", "value": "none"}]
        
        for entity_id, name in entities.items():
            consumption_choices.append({"label": name, "value": entity_id})
            return_choices.append({"label": name, "value": entity_id})
        
        schema_dict = {
            vol.Optional(
                "update_frequency",
                default=self._options.get("update_frequency", "daily")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"label": "Hourly", "value": "hourly"},
                        {"label": "Daily", "value": "daily"},
                        {"label": "Weekly", "value": "weekly"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                "enable_cost_sensors",
                default=self._options.get("enable_cost_sensors", True)
            ): cv.boolean,
            vol.Optional(
                "consumption_entity",
                default=self._options.get("consumption_entity", "none")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=consumption_choices,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                "return_entity", 
                default=self._options.get("return_entity", "none")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=return_choices,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                "average_daily_usage",
                default=self._options.get("average_daily_usage", 30.0)
            ): cv.positive_float,
            vol.Optional(
                "include_additional_charges",
                default=self._options.get("include_additional_charges", True)
            ): cv.boolean,
        }
        
        # Add TOU options if applicable
        if is_tou:
            schema_dict.update({
                vol.Optional(
                    "peak_start",
                    default=self._options.get("peak_start", "15:00")
                ): cv.string,
                vol.Optional(
                    "peak_end",
                    default=self._options.get("peak_end", "19:00")
                ): cv.string,
                vol.Optional(
                    "shoulder_start",
                    default=self._options.get("shoulder_start", "13:00")
                ): cv.string,
                vol.Optional(
                    "shoulder_end",
                    default=self._options.get("shoulder_end", "15:00")
                ): cv.string,
                vol.Optional(
                    "custom_holidays",
                    default=self._options.get("custom_holidays", "")
                ): cv.string,
            })
        
        # Add seasonal options
        schema_dict[vol.Optional(
            "summer_months",
            default=self._options.get("summer_months", "6,7,8,9")
        )] = cv.string
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "rate_schedule": self.config_entry.options.get("rate_schedule", "Unknown"),
            }
        )

    def _get_energy_entities(self) -> dict[str, str]:
        """Get available energy entities."""
        entities = {}
        
        # Get all sensor entities with energy measurement
        for state in self.hass.states.async_all("sensor"):
            if state.attributes.get("unit_of_measurement") in ["kWh", "Wh", "MWh"]:
                friendly_name = state.attributes.get("friendly_name", state.entity_id)
                # Add unit to make it clear
                unit = state.attributes.get("unit_of_measurement", "")
                entities[state.entity_id] = f"{friendly_name} ({unit})"
        
        # Sort by friendly name
        return dict(sorted(entities.items(), key=lambda x: x[1]))