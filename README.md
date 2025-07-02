# Xcel Energy Tariff Integration for Home Assistant

A comprehensive Home Assistant integration for tracking Xcel Energy electricity and gas rates with real-time time-of-use (TOU) monitoring, cost projections, and full configurability.

## Features

### 🎯 Real-Time Rate Tracking
- Current electricity/gas rate updated every minute
- Time-of-use period tracking (Peak/Shoulder/Off-Peak)
- Countdown timer to next rate change
- Holiday and weekend detection

### 📊 Comprehensive Sensors (20+)
- **Rate Sensors**: Current rate, rate with fees, base rate
- **TOU Sensors**: Current period, individual peak/shoulder/off-peak rates
- **Cost Projections**: Hourly, daily, and monthly estimates
- **Status Sensors**: Data source, quality score, last update
- **Information**: Season, fixed charges, additional fees, effective date

### ⚙️ Fully Configurable
- Change rate plans without re-adding integration
- Customize TOU hours and season definitions
- Set average daily usage for projections
- Configure PDF update frequency

### 🚀 Smart Updates
- PDF parsing maximum once per day (configurable to weekly)
- Dynamic values update every minute
- Separate coordinators for static and dynamic data
- Manual refresh available via service call

### 🛠️ Service Calls
- `xcel_energy_tariff.refresh_rates` - Force PDF update
- `xcel_energy_tariff.clear_cache` - Clear all cached data
- `xcel_energy_tariff.calculate_bill` - Calculate bill for usage

## Installation

1. Copy the `custom_components/xcel_energy_tariff` folder to your Home Assistant configuration directory
2. Restart Home Assistant
3. Add the integration via the UI:
   - Settings → Integrations → Add Integration
   - Search for "Xcel Energy Tariff"
   - Select your state and service type

## Configuration

### Initial Setup
- **State**: Your Xcel Energy service state
- **Service Type**: Electric or Gas

### Options (Runtime Configurable)
- **Rate Schedule**: Your current rate plan
- **Update Frequency**: Daily or weekly PDF checks
- **Summer Months**: Define summer season (e.g., "6,7,8,9")
- **Enable Cost Sensors**: Show/hide cost projections
- **Average Daily Usage**: For cost estimates (kWh)

### TOU Options (if applicable)
- **Peak Hours**: Start and end times
- **Shoulder Hours**: Start and end times
- **Custom Holidays**: Additional holidays

## Supported States
- Colorado (CO) - High accuracy with actual PDF rates
- Minnesota (MN)
- Wisconsin (WI)
- Michigan (MI)
- New Mexico (NM)
- Texas (TX)
- North Dakota (ND)
- South Dakota (SD)

## Example Automations

### Peak Period Alert
```yaml
automation:
  - alias: "Peak Rate Alert"
    trigger:
      - platform: state
        entity_id: sensor.xcel_energy_colorado_tou_period
        to: "Peak"
    action:
      - service: notify.mobile_app
        data:
          title: "Peak Rates Active"
          message: "Electricity is now at peak pricing"
```

### Smart Device Control
```yaml
automation:
  - alias: "Run Pool Pump Off-Peak"
    trigger:
      - platform: state
        entity_id: sensor.xcel_energy_colorado_tou_period
        to: "Off-Peak"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.pool_pump
```

## Data Sources

The integration attempts to download and parse official Xcel Energy tariff PDFs. When successful, it extracts:
- Base energy rates
- Time-of-use rates and schedules
- Fixed monthly charges
- Additional charges and riders
- Season definitions
- Effective dates

If PDF parsing fails, sensible fallback rates are used with clear indication.

## Support

For issues or feature requests, please use the GitHub issue tracker.

## Version
2.0.0 - Complete rewrite with enhanced features and no backward compatibility code