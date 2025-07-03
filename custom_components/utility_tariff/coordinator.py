"""Data update coordinators for Utility Tariff integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .providers import ProviderTariffManager

_LOGGER = logging.getLogger(__name__)


class PDFCoordinator(DataUpdateCoordinator):
    """Coordinator for PDF data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        tariff_manager: ProviderTariffManager,
        update_frequency: str = "weekly",
    ) -> None:
        """Initialize PDF coordinator."""
        self.tariff_manager = tariff_manager
        self._last_successful_update: datetime | None = None
        
        # Set update interval based on configuration
        if update_frequency == "daily":
            update_interval = timedelta(hours=24)
        else:  # weekly
            update_interval = timedelta(days=7)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_pdf",
            update_interval=update_interval,
        )
        
        # Initialize with cached/fallback data on startup
        # This will be set by the tariff manager during initialization
        if hasattr(tariff_manager, 'tariff_data') and tariff_manager.tariff_data:
            self.data = tariff_manager.tariff_data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from PDF with retry mechanism."""
        # Check if we've already updated today
        now = dt_util.now()
        if self._last_successful_update:
            if now.date() == self._last_successful_update.date():
                _LOGGER.debug("Already updated PDF today, skipping")
                return self.data or {}
        
        # Retry configuration
        max_retries = 3
        retry_delay = 5  # seconds
        
        last_error = None
        for attempt in range(max_retries):
            try:
                _LOGGER.debug("Attempting to fetch PDF data (attempt %d/%d)", attempt + 1, max_retries)
                
                # Update tariff data from PDF
                result = await self.tariff_manager.async_update_tariffs()
                
                if result:
                    self._last_successful_update = now
                    result["pdf_last_checked"] = now.isoformat()
                    result["pdf_last_successful"] = now.isoformat()
                    result["pdf_fetch_attempts"] = attempt + 1
                    _LOGGER.info("Successfully fetched PDF data on attempt %d", attempt + 1)
                    return result
                else:
                    # If update returned None/False, it might be a temporary issue
                    _LOGGER.warning("PDF update returned no data on attempt %d", attempt + 1)
                    last_error = "No data returned from PDF"
                    
            except Exception as err:
                last_error = err
                _LOGGER.warning(
                    "PDF fetch attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries,
                    str(err)
                )
                
                if attempt < max_retries - 1:
                    # Wait before retrying
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        # All retries failed, keep existing data but update check time
        result = self.data or {}
        result["pdf_last_checked"] = now.isoformat()
        result["pdf_fetch_error"] = str(last_error) if last_error else "Failed to fetch PDF data"
        result["pdf_fetch_attempts"] = max_retries
        
        _LOGGER.error(
            "Failed to fetch PDF data after %d attempts. Last error: %s",
            max_retries,
            last_error
        )
        
        # Don't raise UpdateFailed to prevent the coordinator from stopping
        # We'll use existing data or fallback rates
        return result

    async def async_refresh_data(self) -> None:
        """Force refresh of PDF data."""
        self._last_successful_update = None  # Reset to force update
        await self.async_request_refresh()


class DynamicCoordinator(DataUpdateCoordinator):
    """Coordinator for dynamic data updates (current rates, periods)."""

    def __init__(
        self,
        hass: HomeAssistant,
        tariff_manager: ProviderTariffManager,
        pdf_coordinator: PDFCoordinator,
    ) -> None:
        """Initialize dynamic coordinator."""
        self.tariff_manager = tariff_manager
        self.pdf_coordinator = pdf_coordinator
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_dynamic",
            update_interval=timedelta(minutes=1),  # Update every minute for TOU accuracy
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Calculate dynamic data."""
        try:
            now = dt_util.now()
            
            # Get base data from PDF coordinator
            pdf_data = self.pdf_coordinator.data or {}
            
            # Calculate current values
            current_rate = self.tariff_manager.get_current_rate()
            current_period = self.tariff_manager.get_current_tou_period()
            is_summer = self.tariff_manager.is_summer_season(now)
            is_holiday = self.tariff_manager.is_holiday(now.date())
            
            # If no rate available yet, return minimal data to prevent errors
            if current_rate is None:
                return {
                    "current_rate": None,
                    "current_period": current_period or "Unknown",
                    "current_season": "summer" if is_summer else "winter",
                    "is_holiday": is_holiday,
                    "is_weekend": now.weekday() >= 5,
                    "last_update": now.isoformat(),
                    "data_source": "initializing",
                    **pdf_data,
                }
            
            _LOGGER.debug("Dynamic update - rate: %s, period: %s, summer: %s", 
                         current_rate, current_period, is_summer)
            
            # Log TOU info details
            tou_info = {
                "current_period": current_period,
                "is_tou_schedule": "tou" in getattr(self.tariff_manager, 'rate_schedule', '').lower(),
                "weekday": now.weekday(),
                "hour": now.hour,
                "is_weekend": now.weekday() >= 5,
                "is_holiday": is_holiday,
            }
            _LOGGER.info("TOU info for coordinator: %s", tou_info)
            
            # Calculate time until next period change
            next_period_time = self._calculate_next_period_change(now, current_period)
            
            # Get all current rates
            all_rates = self.tariff_manager.get_all_current_rates()
            
            # Calculate costs
            costs = self._calculate_costs(current_rate, all_rates)
            
            result = {
                "current_rate": current_rate,
                "current_period": current_period,
                "current_season": "summer" if is_summer else "winter",
                "is_holiday": is_holiday,
                "is_weekend": now.weekday() >= 5,
                "current_hour": now.hour,
                "next_period_change": next_period_time,
                "all_current_rates": all_rates,
                "cost_projections": costs,
                "last_update": now.isoformat(),
                "tou_info": tou_info,  # Add TOU info to data
                **pdf_data,  # Include PDF data
            }
            
            _LOGGER.debug("Coordinator data keys: %s", list(result.keys()))
            _LOGGER.debug("TOU info in coordinator data: %s", result.get("tou_info"))
            
            return result
            
        except Exception as err:
            _LOGGER.error("Error calculating dynamic data: %s", err)
            # Try to get at least fallback data
            try:
                fallback_rate = None
                fallback_rates = self.tariff_manager._get_fallback_rates()
                if fallback_rates:
                    # Try to get a basic rate
                    rates = fallback_rates.get("rates", {})
                    if rates:
                        fallback_rate = rates.get("standard") or rates.get("summer") or rates.get("winter")
                
                return {
                    "current_rate": fallback_rate,
                    "current_period": "Unknown",
                    "current_season": "unknown",
                    "error": str(err),
                    "last_update": dt_util.now().isoformat(),
                    "data_source": "fallback_on_error",
                }
            except Exception as fallback_err:
                _LOGGER.error("Error getting fallback data: %s", fallback_err)
                return {
                    "current_rate": None,
                    "current_period": "Unknown",
                    "error": f"Primary: {err}, Fallback: {fallback_err}",
                    "last_update": dt_util.now().isoformat(),
                }

    def _calculate_next_period_change(self, now: datetime, current_period: str) -> dict[str, Any]:
        """Calculate when the next period change will occur."""
        # Get tariff data from manager
        tariff_data = getattr(self.tariff_manager, 'tariff_data', {})
        
        # Check if this is a TOU rate schedule
        rate_schedule = getattr(self.tariff_manager, 'rate_schedule', '')
        is_tou_schedule = 'tou' in rate_schedule.lower()
        
        _LOGGER.debug("Calculating next period change - is_tou: %s, current_period: %s, schedule: %s", 
                     is_tou_schedule, current_period, rate_schedule)
        
        # Skip if not TOU schedule
        if not is_tou_schedule:
            _LOGGER.debug("Non-TOU rate schedule, skipping next period calculation")
            return {"available": False}
        
        # For weekends/holidays, next change is Monday morning
        if now.weekday() >= 5 or self.tariff_manager.is_holiday(now.date()):
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_change = now.replace(hour=0, minute=0, second=0) + timedelta(days=days_until_monday)
            return {
                "available": True,
                "next_change": next_change.isoformat(),
                "next_period": "off-peak",
                "minutes_until": int((next_change - now).total_seconds() / 60),
            }
        
        # For weekdays, calculate based on TOU schedule
        tou_schedule = tariff_data.get("tou_schedule", {})
        schedule_times = {
            "shoulder_start": tou_schedule.get("shoulder", {}).get("start", 13),  # 1 PM default
            "peak_start": tou_schedule.get("peak", {}).get("start", 15),      # 3 PM default
            "peak_end": tou_schedule.get("peak", {}).get("end", 19),        # 7 PM default
        }
        
        current_hour = now.hour
        
        if current_hour < schedule_times["shoulder_start"]:
            # Currently off-peak, next is shoulder
            next_change = now.replace(hour=schedule_times["shoulder_start"], minute=0, second=0)
            next_period = "shoulder"
        elif current_hour < schedule_times["peak_start"]:
            # Currently shoulder, next is peak
            next_change = now.replace(hour=schedule_times["peak_start"], minute=0, second=0)
            next_period = "peak"
        elif current_hour < schedule_times["peak_end"]:
            # Currently peak, next is off-peak
            next_change = now.replace(hour=schedule_times["peak_end"], minute=0, second=0)
            next_period = "off-peak"
        else:
            # Currently off-peak evening, next change is tomorrow
            next_change = (now + timedelta(days=1)).replace(
                hour=schedule_times["shoulder_start"], minute=0, second=0
            )
            next_period = "shoulder"
        
        return {
            "available": True,
            "next_change": next_change.isoformat(),
            "next_period": next_period,
            "minutes_until": int((next_change - now).total_seconds() / 60),
        }

    def _calculate_costs(self, current_rate: float | None, all_rates: dict) -> dict[str, Any]:
        """Calculate cost projections."""
        if not current_rate:
            return {"available": False}
        
        # Get current date info for accurate monthly calculations
        now = dt_util.now()
        current_month = now.month
        current_year = now.year
        
        # Calculate actual days in current month
        if current_month == 12:
            next_month_date = now.replace(year=current_year + 1, month=1, day=1)
        else:
            next_month_date = now.replace(month=current_month + 1, day=1)
        
        last_day_of_month = (next_month_date - timedelta(days=1)).day
        day_of_month = now.day
        days_remaining = last_day_of_month - day_of_month
        
        # Get consumption data
        consumption_entity = self.tariff_manager.options.get("consumption_entity", "none")
        return_entity = self.tariff_manager.options.get("return_entity", "none")
        avg_daily_kwh = self.tariff_manager.options.get("average_daily_usage", 30.0)
        
        # Try to get actual consumption from entity
        actual_daily_kwh = None
        actual_daily_return = 0.0  # Default to no return
        consumption_source = "manual"
        return_source = "none"
        
        # Get consumption data
        if consumption_entity and consumption_entity != "none":
            actual_daily_kwh, consumption_source = self._get_entity_daily_value(
                consumption_entity, "consumption"
            )
        
        # Get return/export data
        if return_entity and return_entity != "none":
            actual_daily_return, return_source = self._get_entity_daily_value(
                return_entity, "return"
            )
        
        # Use actual consumption if available, otherwise fall back to manual
        daily_consumption = actual_daily_kwh if actual_daily_kwh is not None else avg_daily_kwh
        daily_return = actual_daily_return if actual_daily_return is not None else 0.0
        
        # Calculate net consumption (consumption - return)
        net_daily_kwh = daily_consumption - daily_return
        
        # Use net consumption for billing calculations (positive values only for costs)
        billable_kwh = max(0, net_daily_kwh)  # Only pay for net consumption, not export
        
        # Calculate costs based on net usage
        hourly_cost = current_rate * (billable_kwh / 24)
        daily_cost = current_rate * billable_kwh
        
        # More accurate monthly cost calculation
        # Use actual days in month for better projection
        monthly_cost = daily_cost * last_day_of_month
        
        # Calculate potential credit for excess return (if any)
        excess_return = max(0, daily_return - daily_consumption)
        # Note: Credit rate might be different from consumption rate
        # For now, using same rate - could be enhanced to support different export rates
        daily_credit = current_rate * excess_return
        
        # Add fixed charges
        fixed_monthly = all_rates.get("fixed_charges", {}).get("monthly_service", 0)
        
        # Calculate month-to-date and projected costs
        mtd_energy_cost = daily_cost * day_of_month
        projected_remaining_energy_cost = daily_cost * days_remaining
        projected_total_energy_cost = mtd_energy_cost + projected_remaining_energy_cost
        
        return {
            "available": True,
            "per_kwh_now": current_rate,
            "hourly_cost_estimate": round(hourly_cost, 2),
            "daily_cost_estimate": round(daily_cost, 2),
            "monthly_cost_estimate": round(monthly_cost + fixed_monthly, 2),
            "fixed_charges_monthly": fixed_monthly,
            "daily_kwh_used": round(billable_kwh, 2),
            "daily_kwh_consumed": round(daily_consumption, 2),
            "daily_kwh_returned": round(daily_return, 2),
            "net_daily_kwh": round(net_daily_kwh, 2),
            "daily_credit_estimate": round(daily_credit, 2),
            "consumption_source": consumption_source,
            "consumption_entity": consumption_entity if consumption_entity != "none" else None,
            "return_source": return_source,
            "return_entity": return_entity if return_entity != "none" else None,
            # Enhanced monthly projection data
            "days_in_month": last_day_of_month,
            "day_of_month": day_of_month,
            "days_remaining": days_remaining,
            "month_to_date_cost": round(mtd_energy_cost, 2),
            "projected_remaining_cost": round(projected_remaining_energy_cost, 2),
            "projected_total_cost": round(projected_total_energy_cost + fixed_monthly, 2),
            "billing_cycle_progress": round((day_of_month / last_day_of_month) * 100, 1),
        }
    
    def _get_entity_daily_value(self, entity_id: str, entity_type: str) -> tuple[float | None, str]:
        """Get daily value from an entity."""
        # First, check if we have internal daily meters
        config_entry_id = None
        for entry_id, data in self.hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("dynamic_coordinator") == self:
                config_entry_id = entry_id
                break
        
        if config_entry_id:
            utility_meters = self.hass.data[DOMAIN][config_entry_id].get("utility_meters", [])
            # Look for our internal daily meter
            for meter in utility_meters:
                if (hasattr(meter, "_cycle") and meter._cycle == "daily" and 
                    hasattr(meter, "_meter_type") and 
                    ((entity_type == "consumption" and meter._meter_type == "energy_delivered") or
                     (entity_type == "return" and meter._meter_type == "energy_received"))):
                    # Use our internal daily meter
                    if meter.native_value is not None:
                        _LOGGER.debug(
                            "Using internal daily meter for %s: %s kWh",
                            entity_type,
                            meter.native_value
                        )
                        return meter.native_value, f"internal_daily_{entity_type}"
        
        # Fallback to checking the external entity
        state = self.hass.states.get(entity_id)
        if not state or state.state in ["unknown", "unavailable"]:
            return None, "unavailable"
            
        try:
            # Get the entity value
            value = float(state.state)
            unit = state.attributes.get("unit_of_measurement", "kWh")
            
            # Convert to kWh if needed
            if unit == "Wh":
                value = value / 1000
            
            # Check if this is a daily, monthly, or yearly sensor
            state_class = state.attributes.get("state_class")
            friendly_name = state.attributes.get("friendly_name", "").lower()
            
            if "daily" in friendly_name:
                # This is a daily sensor
                return value, f"entity_daily_{entity_type}"
            elif "monthly" in friendly_name:
                # Monthly sensor - divide by days in current month
                now = dt_util.now()
                # Calculate actual days in current month
                if now.month == 12:
                    next_month_date = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    next_month_date = now.replace(month=now.month + 1, day=1)
                days_in_month = (next_month_date - timedelta(days=1)).day
                return value / days_in_month, f"entity_monthly_{entity_type}"
            elif "yearly" in friendly_name or "annual" in friendly_name:
                # Yearly sensor - divide by 365
                return value / 365, f"entity_yearly_{entity_type}"
            elif state_class == "total_increasing":
                # This is a cumulative total - we need to get the daily change
                # Check if we're already using internal daily meters
                if config_entry_id:
                    utility_meters = self.hass.data[DOMAIN][config_entry_id].get("utility_meters", [])
                    has_daily_meter = any(
                        hasattr(meter, "_cycle") and meter._cycle == "daily" and 
                        hasattr(meter, "_meter_type") and 
                        ((entity_type == "consumption" and meter._meter_type == "energy_delivered") or
                         (entity_type == "return" and meter._meter_type == "energy_received"))
                        for meter in utility_meters
                    )
                    if has_daily_meter:
                        # We have internal daily meters, just return None quietly
                        _LOGGER.debug(
                            "%s entity '%s' is cumulative, but internal daily meters are available",
                            entity_type.capitalize(),
                            entity_id
                        )
                        return None, f"entity_total_{entity_type}_handled"
                
                # No internal daily meters, warn the user
                _LOGGER.warning(
                    "%s entity '%s' is a cumulative total. Please use a daily sensor or utility meter for accurate cost calculations.",
                    entity_type.capitalize(),
                    entity_id
                )
                return None, f"entity_total_{entity_type}_unsupported"
            else:
                # Unknown sensor type - log warning
                _LOGGER.warning(
                    "Could not determine sensor type for %s entity '%s'. Please use a daily sensor.",
                    entity_type,
                    entity_id
                )
                return None, f"entity_unknown_{entity_type}"
                
        except (ValueError, TypeError):
            _LOGGER.warning("Could not parse %s entity value: %s", entity_type, state.state)
            return None, "error"