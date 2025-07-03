"""Enhanced sensor platform for Utility Tariff integration v2."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .utility_meter import UtilityTariffMeter, UtilityTariffTOUMeter

# Import all sensor classes from the sensors package
from .sensors import (
    UtilityCurrentRateSensor,
    UtilityCurrentRateWithFeesSensor,
    UtilityCurrentSeasonSensor,
    UtilityDailyCostSensor,
    UtilityDataQualitySensor,
    UtilityDataSourceSensor,
    UtilityEffectiveDateSensor,
    UtilityFixedChargeSensor,
    UtilityGridCreditSensor,
    UtilityHourlyCostSensor,
    UtilityLastUpdateSensor,
    UtilityMonthlyCostSensor,
    UtilityOffPeakRateSensor,
    UtilityPeakRateSensor,
    UtilityShoulderRateSensor,
    UtilityTOUOffPeakCostMeter,
    UtilityTOUPeakCostMeter,
    UtilityTOUPeriodSensor,
    UtilityTOUShoulderCostMeter,
    UtilityTOUTotalCostSensor,
    UtilityTimeUntilNextPeriodSensor,
    UtilityTotalAdditionalChargesSensor,
    UtilityTotalEnergyCostMeter,
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
        
        # TOU Cost sensors will be created later after utility meters
    
    # Cost projection sensors (if enabled)
    if config_entry.options.get("enable_cost_sensors", True):
        sensors.extend([
            UtilityHourlyCostSensor(dynamic_coordinator, config_entry),
            UtilityDailyCostSensor(dynamic_coordinator, config_entry),
            UtilityMonthlyCostSensor(dynamic_coordinator, config_entry),
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
            
            # Create daily meter for delivered energy (for cost calculations)
            daily_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=consumption_entity,
                cycle="daily",
                cycle_name="Energy Delivered Daily",
                meter_type="energy_delivered",
            )
            utility_meters.append(daily_meter)
            
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
            
            # Create daily meter for received energy (for cost calculations)
            daily_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=return_entity,
                cycle="daily",
                cycle_name="Energy Received Daily",
                meter_type="energy_received",
            )
            utility_meters.append(daily_meter)
            
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
            # Total meter
            meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=consumption_entity,
                cycle="total",
                cycle_name="Energy Delivered Total",
                meter_type="energy_delivered",
            )
            utility_meters.append(meter)
            
            # Daily meter for cost calculations
            daily_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=consumption_entity,
                cycle="daily",
                cycle_name="Energy Delivered Daily",
                meter_type="energy_delivered",
            )
            utility_meters.append(daily_meter)
        
        if return_entity != "none":
            # Total meter
            meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=return_entity,
                cycle="total",
                cycle_name="Energy Received Total",
                meter_type="energy_received",
            )
            utility_meters.append(meter)
            
            # Daily meter for cost calculations
            daily_meter = UtilityTariffMeter(
                hass=hass,
                config_entry=config_entry,
                source_entity=return_entity,
                cycle="daily",
                cycle_name="Energy Received Daily",
                meter_type="energy_received",
            )
            utility_meters.append(daily_meter)
    
    # Store meter references for service access
    if utility_meters:
        hass.data[DOMAIN][config_entry.entry_id]["utility_meters"] = utility_meters
        sensors.extend(utility_meters)
        _LOGGER.info("Created %d utility meters", len(utility_meters))
    
    # Create cost tracking meters after utility meters are set up
    cost_meters = []
    if config_entry.options.get("enable_cost_sensors", True):
        if is_tou and consumption_entity != "none":
            # Create TOU cost meters
            try:
                peak_cost_meter = UtilityTOUPeakCostMeter(hass, config_entry, dynamic_coordinator)
                shoulder_cost_meter = UtilityTOUShoulderCostMeter(hass, config_entry, dynamic_coordinator)
                off_peak_cost_meter = UtilityTOUOffPeakCostMeter(hass, config_entry, dynamic_coordinator)
                
                cost_meters.extend([peak_cost_meter, shoulder_cost_meter, off_peak_cost_meter])
                
                # Store references for total cost sensor
                hass.data[DOMAIN][config_entry.entry_id]["tou_cost_meters"] = {
                    "peak": peak_cost_meter,
                    "shoulder": shoulder_cost_meter,
                    "off_peak": off_peak_cost_meter,
                }
                
                # Create total cost sensor that sums the period costs
                total_cost_sensor = UtilityTOUTotalCostSensor(
                    hass=hass,
                    config_entry=config_entry,
                )
                cost_meters.append(total_cost_sensor)
                
                _LOGGER.info("Created TOU cost meters")
            except ValueError as e:
                _LOGGER.warning("Could not create TOU cost meters: %s", e)
        elif consumption_entity != "none":
            # Create standard total cost meter for non-TOU
            try:
                total_cost_meter = UtilityTotalEnergyCostMeter(hass, config_entry, dynamic_coordinator)
                cost_meters.append(total_cost_meter)
                _LOGGER.info("Created total energy cost meter")
            except ValueError as e:
                _LOGGER.warning("Could not create total cost meter: %s", e)
    
    if cost_meters:
        hass.data[DOMAIN][config_entry.entry_id]["cost_meters"] = cost_meters
        sensors.extend(cost_meters)
    
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