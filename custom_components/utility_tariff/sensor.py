"""Enhanced sensor platform for Utility Tariff integration v2."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ALL_STATES
from .coordinator import DynamicCoordinator, PDFCoordinator
from .utility_meter import UtilityTariffMeter, UtilityTariffTOUMeter

# Import all sensor classes from the sensors package
from .sensors import (
    UtilityCurrentRateSensor,
    UtilityCurrentRateWithFeesSensor,
    UtilityTOUPeriodSensor,
    UtilityTimeUntilNextPeriodSensor,
    UtilityPeakRateSensor,
    UtilityShoulderRateSensor,
    UtilityOffPeakRateSensor,
    UtilityHourlyCostSensor,
    UtilityDailyCostSensor,
    UtilityMonthlyCostSensor,
    UtilityDataSourceSensor,
    UtilityLastUpdateSensor,
    UtilityDataQualitySensor,
    UtilityCurrentSeasonSensor,
    UtilityFixedChargeSensor,
    UtilityTotalAdditionalChargesSensor,
    UtilityEffectiveDateSensor,
    UtilityGridCreditSensor,
    UtilityTOUPeakCostSensor,
    UtilityTOUShoulderCostSensor,
    UtilityTOUOffPeakCostSensor,
    UtilityTotalEnergyCostSensor,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Utility Tariff sensors from a config entry."""
    pdf_coordinator = hass.data[DOMAIN][config_entry.entry_id]["pdf_coordinator"]
    dynamic_coordinator = hass.data[DOMAIN][config_entry.entry_id]["dynamic_coordinator"]
    tariff_manager = hass.data[DOMAIN][config_entry.entry_id]["tariff_manager"]
    
    sensors = []
    
    # Core rate sensors
    sensors.extend([
        UtilityCurrentRateSensor(dynamic_coordinator, config_entry),
        UtilityCurrentRateWithFeesSensor(dynamic_coordinator, config_entry),
    ])
    
    # TOU sensors (if applicable)
    if "tou" in config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "")):
        sensors.extend([
            UtilityTOUPeriodSensor(dynamic_coordinator, config_entry),
            UtilityTimeUntilNextPeriodSensor(dynamic_coordinator, config_entry),
            UtilityPeakRateSensor(dynamic_coordinator, config_entry),
            UtilityShoulderRateSensor(dynamic_coordinator, config_entry),
            UtilityOffPeakRateSensor(dynamic_coordinator, config_entry),
        ])
        
        # TOU Cost sensors (if cost sensors enabled)
        if config_entry.options.get("enable_cost_sensors", True):
            sensors.extend([
                UtilityTOUPeakCostSensor(dynamic_coordinator, config_entry),
                UtilityTOUShoulderCostSensor(dynamic_coordinator, config_entry),
                UtilityTOUOffPeakCostSensor(dynamic_coordinator, config_entry),
            ])
    
    # Cost projection sensors (if enabled)
    if config_entry.options.get("enable_cost_sensors", True):
        sensors.extend([
            UtilityHourlyCostSensor(dynamic_coordinator, config_entry),
            UtilityDailyCostSensor(dynamic_coordinator, config_entry),
            UtilityMonthlyCostSensor(dynamic_coordinator, config_entry),
            UtilityTotalEnergyCostSensor(dynamic_coordinator, config_entry),
        ])
    
    # Net metering sensors (if return entity configured)
    if config_entry.options.get("return_entity", "none") != "none":
        sensors.extend([
            UtilityGridCreditSensor(dynamic_coordinator, config_entry),
        ])
    
    # Internal utility meters for energy tracking
    consumption_entity = config_entry.options.get("consumption_entity", "none")
    return_entity = config_entry.options.get("return_entity", "none")
    
    # Create internal utility meters directly instead of tracking sensors
    utility_meters = []
    
    # Determine if this is a TOU rate schedule
    is_tou = "tou" in config_entry.options.get("rate_schedule", config_entry.data.get("rate_schedule", "")).lower()
    
    if is_tou:
        # Create TOU utility meters for different periods
        tou_periods = [
            ("peak", "Peak"),
            ("shoulder", "Shoulder"), 
            ("off_peak", "Off-Peak"),
        ]
        
        # Create meters for energy delivered (consumption) if consumption entity configured
        if consumption_entity != "none":
            # Create total meter for delivered energy
            total_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=consumption_entity,
                cycle="total",
                cycle_name="Energy Delivered Total",
                meter_type="energy_delivered",
            )
            utility_meters.append(total_meter)
            
            # Create TOU period meters for delivered energy
            for period, period_name in tou_periods:
                meter = UtilityTariffTOUMeter(
                    hass=hass,
                    config_entry=config_entry,
                    source_entity=consumption_entity,
                    tou_period=period,
                    period_name=f"Energy Delivered {period_name}",
                    meter_type="energy_delivered",
                )
                utility_meters.append(meter)
        
        # Create meters for energy received (return) if return entity configured
        if return_entity != "none":
            # Create total meter for received energy
            total_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=return_entity,
                cycle="total",
                cycle_name="Energy Received Total",
                meter_type="energy_received",
            )
            utility_meters.append(total_meter)
            
            # Create TOU period meters for received energy
            for period, period_name in tou_periods:
                meter = UtilityTariffTOUMeter(
                    hass=hass,
                    config_entry=config_entry,
                    source_entity=return_entity,
                    tou_period=period,
                    period_name=f"Energy Received {period_name}",
                    meter_type="energy_received",
                )
                utility_meters.append(meter)
    else:
        # Create total utility meters (non-TOU)
        if consumption_entity != "none":
            meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=consumption_entity,
                cycle="total",
                cycle_name="Energy Delivered Total",
                meter_type="energy_delivered",
            )
            utility_meters.append(meter)
        
        if return_entity != "none":
            meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=return_entity,
                cycle="total",
                cycle_name="Energy Received Total",
                meter_type="energy_received",
            )
            utility_meters.append(meter)
    
    # Store meter references for service access
    if utility_meters:
        hass.data[DOMAIN][config_entry.entry_id]["utility_meters"] = utility_meters
        sensors.extend(utility_meters)
        _LOGGER.info("Created %d utility meters", len(utility_meters))
    
    # Status and info sensors
    sensors.extend([
        UtilityDataSourceSensor(pdf_coordinator, config_entry),
        UtilityLastUpdateSensor(pdf_coordinator, config_entry),
        UtilityDataQualitySensor(pdf_coordinator, config_entry),
        UtilityCurrentSeasonSensor(dynamic_coordinator, config_entry),
        UtilityFixedChargeSensor(dynamic_coordinator, config_entry),
        UtilityTotalAdditionalChargesSensor(dynamic_coordinator, config_entry),
        UtilityEffectiveDateSensor(pdf_coordinator, config_entry),
    ])
    
    # Add all sensors and utility meters
    async_add_entities(sensors)