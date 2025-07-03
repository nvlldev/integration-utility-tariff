# Configuration Examples

This document provides configuration examples for different utility providers and use cases.

## Table of Contents
- [Basic Configurations](#basic-configurations)
- [Advanced Configurations](#advanced-configurations)
- [Solar/Net Metering](#solarnet-metering)
- [Time-of-Use Optimization](#time-of-use-optimization)
- [Multi-Location Setup](#multi-location-setup)

## Basic Configurations

### Xcel Energy - Colorado Electric
```yaml
# Basic residential electric setup
provider: xcel_energy
state: CO
service_type: electric
rate_schedule: residential

# Options
update_frequency: daily
enable_cost_sensors: true
average_daily_usage: 30.0
```

### Xcel Energy - Minnesota Gas
```yaml
# Natural gas service
provider: xcel_energy
state: MN
service_type: gas
rate_schedule: residential_gas

# Options
update_frequency: weekly
enable_cost_sensors: true
average_daily_usage: 3.5  # therms
```

### Pacific Gas & Electric (When Available)
```yaml
# PG&E California setup
provider: pge
state: CA
service_type: electric
rate_schedule: E-1  # Basic residential

# Options
update_frequency: daily
enable_cost_sensors: true
average_daily_usage: 25.0
```

## Advanced Configurations

### Time-of-Use with Custom Schedule
```yaml
# Xcel Energy TOU setup
provider: xcel_energy
state: CO
service_type: electric
rate_schedule: residential_tou

# Options
update_frequency: hourly  # More frequent for TOU
enable_cost_sensors: true
average_daily_usage: 35.0

# Custom TOU periods (if supported)
tou_periods:
  peak_start: "15:00"    # 3 PM
  peak_end: "19:00"      # 7 PM
  shoulder_start: "13:00" # 1 PM
  shoulder_end: "15:00"   # 3 PM
```

### Electric Vehicle Rate Plan
```yaml
# EV-specific rate schedule
provider: xcel_energy
state: CO
service_type: electric
rate_schedule: residential_ev

# Options
update_frequency: hourly
enable_cost_sensors: true
average_daily_usage: 50.0  # Higher for EV charging
```

## Solar/Net Metering

### Basic Solar Setup
```yaml
# With solar production monitoring
provider: xcel_energy
state: CO
service_type: electric
rate_schedule: residential

# Options
update_frequency: hourly
enable_cost_sensors: true
average_daily_usage: 30.0
consumption_entity: sensor.home_energy_consumption_daily
return_entity: sensor.solar_energy_production_daily
```

### Advanced Net Metering
```yaml
# Detailed solar configuration
provider: xcel_energy
state: CO
service_type: electric
rate_schedule: residential_tou

# Options
update_frequency: hourly
enable_cost_sensors: true

# Consumption tracking
consumption_entity: sensor.smart_meter_daily_consumption
consumption_type: net  # or gross

# Solar export tracking
return_entity: sensor.inverter_daily_export
export_rate_multiplier: 0.8  # If export rate differs

# Advanced options
track_peak_demand: true
demand_window_minutes: 15
```

## Time-of-Use Optimization

### Automation Examples

#### Basic TOU Notification
```yaml
automation:
  - alias: "TOU Period Notifications"
    trigger:
      - platform: state
        entity_id: sensor.utility_tariff_tou_period
    action:
      - service: notify.mobile_app
        data:
          title: "Electricity Rate Change"
          message: >
            Rates are now {{ states('sensor.utility_tariff_tou_period') }}.
            Current rate: ${{ states('sensor.utility_tariff_current_rate') }}/kWh
```

#### Smart Appliance Control
```yaml
automation:
  - alias: "Run Pool Pump During Off-Peak"
    trigger:
      - platform: state
        entity_id: sensor.utility_tariff_tou_period
        to: "Off-Peak"
    condition:
      - condition: time
        after: "22:00"
        before: "06:00"
    action:
      - service: switch.turn_on
        entity_id: switch.pool_pump
      - delay: "04:00:00"
      - service: switch.turn_off
        entity_id: switch.pool_pump
```

#### EV Charging Optimization
```yaml
automation:
  - alias: "Smart EV Charging"
    trigger:
      - platform: numeric_state
        entity_id: sensor.utility_tariff_current_rate
        below: 0.08  # Charge when rate below 8¢/kWh
    condition:
      - condition: state
        entity_id: binary_sensor.ev_plugged_in
        state: "on"
      - condition: numeric_state
        entity_id: sensor.ev_battery_level
        below: 80
    action:
      - service: switch.turn_on
        entity_id: switch.ev_charger
      
  - alias: "Stop EV Charging on Peak"
    trigger:
      - platform: state
        entity_id: sensor.utility_tariff_tou_period
        to: "Peak"
    action:
      - service: switch.turn_off
        entity_id: switch.ev_charger
```

## Multi-Location Setup

### Multiple Properties
```yaml
# Location 1: Primary Residence
- provider: xcel_energy
  state: CO
  service_type: electric
  rate_schedule: residential_tou
  name_suffix: "Home"

# Location 2: Vacation Home
- provider: pge
  state: CA
  service_type: electric
  rate_schedule: E-6
  name_suffix: "Cabin"

# Location 3: Rental Property
- provider: duke_energy
  state: NC
  service_type: electric
  rate_schedule: residential
  name_suffix: "Rental"
```

### Dashboard Example
```yaml
# Lovelace card for multi-location monitoring
type: vertical-stack
cards:
  - type: markdown
    content: "## Electricity Rates"
  
  - type: entities
    title: "Current Rates"
    entities:
      - entity: sensor.utility_tariff_home_current_rate
        name: "Home (Colorado)"
      - entity: sensor.utility_tariff_cabin_current_rate
        name: "Cabin (California)"
      - entity: sensor.utility_tariff_rental_current_rate
        name: "Rental (North Carolina)"
  
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.utility_tariff_home_predicted_bill
        name: "Home"
        max: 200
      - type: gauge
        entity: sensor.utility_tariff_cabin_predicted_bill
        name: "Cabin"
        max: 150
      - type: gauge
        entity: sensor.utility_tariff_rental_predicted_bill
        name: "Rental"
        max: 100
```

## Energy Dashboard Integration

### Cost Tracking Configuration
```yaml
# In Home Assistant Energy Dashboard settings
grid_consumption:
  - entity: sensor.smart_meter_consumption
    cost_entity: sensor.utility_tariff_current_rate_with_fees

grid_production:
  - entity: sensor.solar_production
    compensation_entity: sensor.utility_tariff_current_rate
```

### Custom Statistics
```yaml
# Track costs by TOU period
template:
  - sensor:
      - name: "Peak Period Cost Today"
        state: >
          {% set peak_kwh = state_attr('sensor.daily_consumption', 'peak_kwh')|float(0) %}
          {% set peak_rate = state_attr('sensor.utility_tariff_peak_rate', 'rate')|float(0) %}
          {{ (peak_kwh * peak_rate) | round(2) }}
        unit_of_measurement: "$"
        
      - name: "Off-Peak Savings Today"
        state: >
          {% set off_peak_kwh = state_attr('sensor.daily_consumption', 'off_peak_kwh')|float(0) %}
          {% set peak_rate = states('sensor.utility_tariff_peak_rate')|float(0) %}
          {% set off_peak_rate = states('sensor.utility_tariff_off_peak_rate')|float(0) %}
          {{ (off_peak_kwh * (peak_rate - off_peak_rate)) | round(2) }}
        unit_of_measurement: "$"
```

## Troubleshooting Common Issues

### Rate Not Updating
```yaml
# Force more frequent updates
update_frequency: hourly  # Instead of daily

# Or use service call
service: utility_tariff.refresh_rates
target:
  entity_id: sensor.utility_tariff_current_rate
```

### Wrong TOU Period
```yaml
# Override timezone if needed
time_zone: "America/Denver"

# Custom holiday calendar
holidays:
  - "2024-01-01"  # New Year
  - "2024-07-04"  # Independence Day
  - "2024-12-25"  # Christmas
```

### Solar Export Not Tracked
```yaml
# Ensure correct entity
return_entity: sensor.solar_meter_export  # Not production!

# Check entity state class
# The export entity should have state_class: total_increasing
```

## Best Practices

1. **Update Frequency**
   - Daily: For stable rates without TOU
   - Hourly: For TOU plans
   - Every 5 minutes: For real-time pricing (when available)

2. **Entity Selection**
   - Use entities with `state_class: total_increasing` for consumption
   - Ensure units are in kWh (not Wh or MWh)
   - For solar, use grid export, not total production

3. **Cost Projections**
   - Set realistic average daily usage
   - Update seasonally for accuracy
   - Account for seasonal rate changes

4. **Performance**
   - Limit update frequency to what's needed
   - Disable unused sensors in options
   - Use recorder exclusions for frequently updating sensors

## Provider-Specific Notes

### Xcel Energy
- PDF updates typically occur monthly
- TOU periods are consistent across states
- Summer months: June-September
- Peak hours: 3-7 PM weekdays

### Pacific Gas & Electric (Future)
- Different TOU schedules by plan
- Baseline allowances vary by climate zone
- Medical baseline available
- EV rates have super off-peak periods

### Real-Time Pricing (Future)
- Updates every 5-15 minutes
- Prices can be negative
- Requires different automation strategies
- Best for flexible loads