# Migration Guide: Xcel Energy Tariff → Utility Tariff

This guide helps users upgrade from the Xcel Energy Tariff integration to the new multi-provider Utility Tariff integration.

## Overview

The Utility Tariff integration (v1.0.0) is a complete rewrite that supports multiple utility providers while maintaining full backward compatibility with existing Xcel Energy configurations.

## What's Changed

### Name Changes
- **Integration Name**: "Xcel Energy Tariff" → "Utility Tariff"
- **Domain**: `xcel_energy_tariff` → `utility_tariff`
- **Entity Prefixes**: Now use provider short names (e.g., "Xcel Colorado" instead of "Xcel Energy Colorado")

### New Features
- Support for multiple utility providers
- Multiple data source types (API, HTML, CSV, real-time pricing)
- Enhanced net metering support
- Provider selection in configuration
- More flexible rate extraction

## Automatic Migration

**Good news!** The integration handles migration automatically:

1. **Existing configurations are preserved** - Your Xcel Energy setup will continue working
2. **Entity IDs remain unchanged** - Automations and scripts will not break
3. **Historical data is retained** - Energy statistics are preserved
4. **Provider is set automatically** - Xcel Energy is selected for existing installs

## What You Need to Do

### For Most Users: Nothing!

The migration happens automatically when you update. Your existing setup will continue working exactly as before.

### For Advanced Users

If you want to take advantage of new features:

1. **Review New Sensors**
   - Check for new net metering sensors if you have solar
   - Review enhanced cost projection sensors
   - Consider enabling new data quality sensors

2. **Update Automations (Optional)**
   - New sensors provide more detailed information
   - TOU period tracking is more accurate
   - Cost projections account for net metering

3. **Explore Provider Options**
   - Check if your utility has API support (faster updates)
   - Review provider-specific features
   - Consider update frequency options

## Configuration Changes

### Old Configuration
```yaml
# Configuration Entry Data (not editable):
domain: xcel_energy_tariff
data:
  state: "CO"
  service_type: "electric"
  rate_schedule: "residential"
```

### New Configuration (Automatic)
```yaml
# Configuration Entry Data (migrated automatically):
domain: utility_tariff
data:
  provider: "xcel_energy"  # Added automatically
  state: "CO"
  service_type: "electric"
  rate_schedule: "residential"
```

## Breaking Changes

### For Custom Components/Scripts

If you have custom components that directly use the integration:

**Old Import**:
```python
from custom_components.xcel_energy_tariff.tariff_manager import XcelTariffManager
```

**New Import**:
```python
from custom_components.utility_tariff.providers import ProviderTariffManager
```

### For YAML Configuration

Direct YAML configuration is no longer supported. Use the UI configuration flow.

## Troubleshooting

### Integration Not Found After Update

If the integration disappears after update:
1. Clear browser cache
2. Restart Home Assistant
3. Check logs for migration errors

### Entities Unavailable

If entities show as unavailable:
1. Check the integration is loaded (Settings → Integrations)
2. Reload the integration
3. Check logs for provider errors

### Rate Data Not Updating

The new integration may use different data sources:
1. Check data source sensor
2. Review update frequency in options
3. Force refresh using service call

## New Features to Explore

### 1. Net Metering Support
If you have solar panels:
- Configure return entity for export tracking
- New sensors for grid credit calculations
- Accurate net consumption tracking

### 2. Enhanced Cost Projections
- More accurate bill predictions
- Accounts for TOU periods
- Includes fixed charges

### 3. Data Quality Monitoring
- Track extraction confidence
- Monitor data freshness
- Automatic fallback handling

### 4. Multi-Provider Support
- Easy to switch providers if you move
- Compare rates across providers
- Support for multiple locations

## Getting Help

### Resources
- [GitHub Issues](https://github.com/your-username/utility-tariff/issues)
- [Home Assistant Community](https://community.home-assistant.io/)
- [Integration Documentation](README.md)

### Common Issues

**Q: My automations stopped working**
A: Entity IDs are preserved, but check if you're using the domain name in automations.

**Q: Can I still use PDF extraction?**
A: Yes! Xcel Energy still uses PDF extraction by default.

**Q: Will my energy dashboard break?**
A: No, all sensor data remains compatible with the energy dashboard.

## Future Considerations

### Coming Soon
- Additional utility providers
- Real-time pricing support
- Enhanced solar integration
- Demand charge tracking

### Provider Roadmap
- Pacific Gas & Electric (PG&E)
- Consolidated Edison (ConEd)
- Duke Energy
- Commonwealth Edison (ComEd)

## Rollback Instructions

If you need to rollback (not recommended):

1. **Backup First**: Always backup your Home Assistant configuration
2. **Uninstall**: Remove the Utility Tariff integration
3. **Install Old Version**: Install the previous Xcel Energy Tariff version
4. **Restore Configuration**: Your old configuration should still work

Note: Rolling back means losing access to new features and bug fixes.

## Summary

The migration to Utility Tariff is designed to be seamless:
- ✅ Automatic configuration migration
- ✅ Preserved entity IDs
- ✅ Backward compatible
- ✅ Enhanced features
- ✅ Multi-provider support

Most users won't notice any changes except for new features and improved reliability!