"""Data update coordinators for Xcel Energy Tariff integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .tariff_manager import XcelTariffManager

_LOGGER = logging.getLogger(__name__)


class XcelPDFCoordinator(DataUpdateCoordinator):
    """Coordinator for PDF data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        tariff_manager: XcelTariffManager,
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from PDF."""
        try:
            # Check if we've already updated today
            now = dt_util.now()
            if self._last_successful_update:
                if now.date() == self._last_successful_update.date():
                    _LOGGER.debug("Already updated PDF today, skipping")
                    return self.data or {}
            
            # Update tariff data from PDF
            result = await self.tariff_manager.async_update_tariffs()
            
            if result:
                self._last_successful_update = now
                result["pdf_last_checked"] = now.isoformat()
                result["pdf_last_successful"] = now.isoformat()
            else:
                # If update failed, keep existing data but update check time
                result = self.data or {}
                result["pdf_last_checked"] = now.isoformat()
                
            return result
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching PDF data: {err}") from err

    async def async_refresh_data(self) -> None:
        """Force refresh of PDF data."""
        self._last_successful_update = None  # Reset to force update
        await self.async_request_refresh()


class XcelDynamicCoordinator(DataUpdateCoordinator):
    """Coordinator for dynamic data updates (current rates, periods)."""

    def __init__(
        self,
        hass: HomeAssistant,
        tariff_manager: XcelTariffManager,
        pdf_coordinator: XcelPDFCoordinator,
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
            
            _LOGGER.debug("Dynamic update - rate: %s, period: %s, summer: %s", 
                         current_rate, current_period, is_summer)
            
            # Calculate time until next period change
            next_period_time = self._calculate_next_period_change(now, current_period)
            
            # Get all current rates
            all_rates = self.tariff_manager.get_all_current_rates()
            
            # Calculate costs
            costs = self._calculate_costs(current_rate, all_rates)
            
            return {
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
                **pdf_data,  # Include PDF data
            }
            
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
        # Skip if not TOU
        if not hasattr(self.tariff_manager, '_tariff_data') or not self.tariff_manager._tariff_data.get('tou_rates'):
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
        schedule_times = {
            "shoulder_start": 13,  # 1 PM
            "peak_start": 15,      # 3 PM
            "peak_end": 19,        # 7 PM
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
        
        # Get average daily usage from options (default 30 kWh)
        avg_daily_kwh = 30.0  # Will be configurable
        
        # Calculate costs
        hourly_cost = current_rate * (avg_daily_kwh / 24)
        daily_cost = current_rate * avg_daily_kwh
        monthly_cost = daily_cost * 30
        
        # Add fixed charges
        fixed_monthly = all_rates.get("fixed_charges", {}).get("monthly_service", 0)
        
        return {
            "available": True,
            "per_kwh_now": current_rate,
            "hourly_cost_estimate": round(hourly_cost, 2),
            "daily_cost_estimate": round(daily_cost, 2),
            "monthly_cost_estimate": round(monthly_cost + fixed_monthly, 2),
            "fixed_charges_monthly": fixed_monthly,
        }