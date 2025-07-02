"""Config flow for Xcel Energy Tariff integration v2."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
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
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError as exc:
                errors["base"] = str(exc)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Store basic data and proceed to rate selection
                self._data = user_input
                self._data["title"] = info["title"]
                return await self.async_step_rate_plan()

        schema = vol.Schema(
            {
                vol.Required("state"): vol.In(list(STATES.keys())),
                vol.Required("service_type", default=SERVICE_TYPE_ELECTRIC): vol.In(list(SERVICE_TYPES.keys())),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_rate_plan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle rate plan selection."""
        if user_input is not None:
            self._data["rate_schedule"] = user_input["rate_schedule"]
            self._options.update(user_input)
            
            # If TOU rate, go to TOU configuration
            if "tou" in user_input["rate_schedule"]:
                return await self.async_step_tou_config()
            else:
                return await self.async_step_additional_options()

        # Build rate options based on service type
        rate_options = get_rate_options(self._data["service_type"])
        default_rate = "residential" if self._data["service_type"] == SERVICE_TYPE_ELECTRIC else "residential_gas"

        schema = vol.Schema(
            {
                vol.Required("rate_schedule", default=default_rate): vol.In(rate_options),
                vol.Required("update_frequency", default="weekly"): vol.In({
                    "daily": "Daily", 
                    "weekly": "Weekly"
                }),
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
            self._options.update(user_input)
            return await self.async_step_additional_options()

        schema = vol.Schema(
            {
                vol.Optional("peak_start", default="15:00"): cv.string,
                vol.Optional("peak_end", default="19:00"): cv.string,
                vol.Optional("shoulder_start", default="13:00"): cv.string,
                vol.Optional("shoulder_end", default="15:00"): cv.string,
                vol.Optional("custom_holidays", default=""): cv.string,
            }
        )

        return self.async_show_form(
            step_id="tou_config",
            data_schema=schema,
            description_placeholders={
                "info": "Configure Time-of-Use schedule. Times are in 24-hour format (HH:MM)."
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

        schema = vol.Schema(
            {
                vol.Optional("summer_months", default="6,7,8,9"): cv.string,
                vol.Optional("enable_cost_sensors", default=True): cv.boolean,
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
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_schedule = self.config_entry.options.get(
            "rate_schedule", 
            self.config_entry.data.get("rate_schedule", "residential")
        )
        
        # Build rate schedule options based on service type
        service_type = self.config_entry.data["service_type"]
        rate_options = get_rate_options(service_type)

        schema = vol.Schema(
            {
                vol.Required("rate_schedule", default=current_schedule): vol.In(rate_options),
                vol.Required(
                    "update_frequency",
                    default=self.config_entry.options.get("update_frequency", "weekly")
                ): vol.In({"daily": "Daily", "weekly": "Weekly"}),
                vol.Optional(
                    "summer_months",
                    default=self.config_entry.options.get("summer_months", "6,7,8,9")
                ): cv.string,
                vol.Optional(
                    "enable_cost_sensors",
                    default=self.config_entry.options.get("enable_cost_sensors", True)
                ): cv.boolean,
                vol.Optional(
                    "average_daily_usage",
                    default=self.config_entry.options.get("average_daily_usage", 30.0)
                ): cv.positive_float,
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

        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""