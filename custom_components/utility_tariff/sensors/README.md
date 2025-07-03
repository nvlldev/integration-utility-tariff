# Utility Tariff Sensors

This directory contains all sensor definitions for the Utility Tariff integration, organized by functionality.

## File Structure

- `__init__.py` - Package initialization and exports
- `base.py` - Base sensor class used by all other sensors
- `rate.py` - Rate-related sensors (current rate, peak/shoulder/off-peak rates)
- `tou.py` - Time-of-Use specific sensors (TOU period, time until next period)
- `cost.py` - Cost calculation sensors (hourly/daily/monthly costs, predicted bill)
- `energy.py` - Energy tracking sensors (delivered/received energy totals)
- `info.py` - Informational sensors (data source, last update, season, etc.)
- `charge.py` - Charge-related sensors (fixed charges, additional charges)
- `credit.py` - Grid credit sensor for net metering

## Adding New Sensors

1. Determine the appropriate category for your sensor
2. Add the sensor class to the relevant file
3. Import it in `__init__.py`
4. Add it to the `__all__` list in `__init__.py`
5. Update the main `sensor.py` file to instantiate your sensor

## Sensor Base Class

All sensors inherit from `UtilitySensorBase` in `base.py`, which provides:
- Common initialization
- Device info setup
- Entity naming conventions
- Integration with the coordinator pattern