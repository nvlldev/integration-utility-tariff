# Utility Tariff Integration for Home Assistant

A comprehensive Home Assistant integration for tracking electricity and gas rates from various utility providers across North America. This integration extracts current tariff rates from utility PDF documents and provides real-time rate information for accurate cost tracking and energy management.

## Features

- **Multi-Provider Support**: Extensible architecture supporting multiple utility companies
- **Time-of-Use (TOU) Rates**: Track peak, off-peak, and shoulder period rates
- **Seasonal Rates**: Automatic summer/winter rate adjustments
- **Cost Projections**: Hourly, daily, and monthly cost estimates
- **Net Metering**: Solar export tracking and grid credit calculations
- **Predicted Bills**: Monthly bill predictions based on usage patterns
- **Multiple Data Sources**: Supports PDF parsing, API integration, HTML scraping, CSV imports, and real-time pricing
- **Fallback Rates**: Built-in fallback rates when PDFs are unavailable
- **Repair Flow**: Graceful error handling with user-friendly recovery options

## Supported Providers

### Currently Implemented
- **Xcel Energy** - Colorado, Michigan, Minnesota, New Mexico, North Dakota, South Dakota, Texas, Wisconsin

### Coming Soon
- Pacific Gas & Electric (PG&E) - California
- Consolidated Edison (ConEd) - New York
- Duke Energy - North Carolina, South Carolina, Florida, Indiana, Ohio, Kentucky
- ComEd - Illinois
- Southern California Edison (SCE) - California
- PSEG - New Jersey/Long Island

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the "+" button
4. Search for "Utility Tariff"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation
1. Copy the `custom_components/utility_tariff` folder to your Home Assistant configuration directory
2. Restart Home Assistant

## Configuration

### Initial Setup
1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Utility Tariff"
4. Select your utility provider
5. Choose your state and service type (electric/gas)
6. Select your rate schedule
7. Configure consumption tracking (optional)
8. Configure solar export tracking (optional)

### Quick Setup vs Custom Setup
- **Quick Setup**: Uses sensible defaults for most users
- **Custom Setup**: Advanced configuration for TOU schedules, holidays, and seasonal adjustments

## Entities Created

### Rate Sensors
- **Current Rate**: Real-time electricity/gas rate
- **Current Rate (with fees)**: Total rate including all charges
- **Base Energy Rate**: Energy charge without additional fees

### Time-of-Use Sensors (if applicable)
- **TOU Period**: Current time-of-use period
- **Time Until Next Period**: Minutes until rate change
- **Peak/Shoulder/Off-Peak Rates**: Individual TOU rates

### Cost Projection Sensors
- **Estimated Hourly Cost**: Current hour's estimated cost
- **Estimated Daily Cost**: Today's projected cost
- **Estimated Monthly Cost**: Current month's projected cost
- **Predicted Monthly Bill**: Full bill prediction including fixed charges

### Net Metering Sensors (if configured)
- **Net Energy Consumption**: Consumption minus solar export
- **Daily Grid Credit**: Credit for excess solar export
- **Daily Solar Export**: Energy returned to the grid

### Information Sensors
- **Data Source**: PDF or fallback rates
- **Last Update**: When rates were last updated
- **Data Quality**: Extraction confidence score
- **Current Season**: Summer/Winter season
- **Monthly Service Charge**: Fixed monthly charges

## Service Calls

### utility_tariff.refresh_rates
Force an immediate update of tariff rates from the provider.

```yaml
service: utility_tariff.refresh_rates
target:
  entity_id: sensor.utility_tariff_current_rate
```

### utility_tariff.clear_cache
Clear cached tariff data and force fresh download.

```yaml
service: utility_tariff.clear_cache
target:
  entity_id: sensor.utility_tariff_current_rate
```

## Example Automations

### Notify on Rate Changes
```yaml
automation:
  - alias: "Notify on Peak Rates"
    trigger:
      - platform: state
        entity_id: sensor.utility_tariff_tou_period
        to: "Peak"
    action:
      - service: notify.mobile_app
        data:
          message: "Electricity rates are now at peak pricing!"
```

### Optimize Device Usage
```yaml
automation:
  - alias: "Run Dishwasher During Off-Peak"
    trigger:
      - platform: state
        entity_id: sensor.utility_tariff_tou_period
        to: "Off-Peak"
    condition:
      - condition: state
        entity_id: input_boolean.dishwasher_ready
        state: "on"
    action:
      - service: switch.turn_on
        entity_id: switch.dishwasher
```

## Adding New Providers

See [providers/README.md](custom_components/utility_tariff/providers/README.md) for detailed instructions on adding support for new utility providers.

The integration supports multiple data source types:
- **PDF Documents**: Extract rates from tariff PDFs (like Xcel Energy)
- **REST APIs**: Direct integration with utility APIs
- **HTML Scraping**: Extract rates from utility websites
- **CSV/Excel**: Import rate schedules from spreadsheets
- **Real-time Pricing**: Dynamic pricing APIs (like ERCOT in Texas)
3. Implement rate calculator for their rate structures
4. Add URL builder for accessing tariff documents
5. Register the provider in `providers/registry.py`

## Troubleshooting

### PDF Download Errors
- Check your internet connection
- Verify the utility's website is accessible
- Try using the repair flow to set manual rates

### Incorrect Rates
- Verify you've selected the correct rate schedule
- Check if your plan has been recently updated
- Use the data quality sensor to assess extraction confidence

### Missing Sensors
- Some sensors only appear for TOU rate plans
- Net metering sensors require return entity configuration
- Cost sensors can be disabled in options

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Key areas for contribution:
- Adding new utility providers
- Improving PDF parsing patterns
- Adding new rate structures (demand charges, real-time pricing)
- Enhancing cost projection algorithms

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Originally developed for Xcel Energy customers
- Inspired by the need for accurate real-time energy cost tracking
- Built for the Home Assistant community

## Support

- **Issues**: [GitHub Issues](https://github.com/your-username/utility-tariff/issues)
- **Discussions**: [Home Assistant Community](https://community.home-assistant.io/)
- **Documentation**: [Wiki](https://github.com/your-username/utility-tariff/wiki)