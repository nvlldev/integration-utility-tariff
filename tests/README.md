# Xcel Energy Tariff Integration Tests

This directory contains comprehensive tests for the Xcel Energy Tariff Home Assistant integration.

## Test Coverage

### Holiday Detection (`test_tariff_manager.py`)
- ✅ Fixed holidays (New Year's, Independence Day, Christmas)
- ✅ Floating holidays (Memorial Day, Labor Day, Thanksgiving)
- ✅ Observed holidays when they fall on weekends
- ✅ Non-holiday weekdays correctly identified

### TOU Period Detection (`test_tariff_manager.py`)
- ✅ Peak hours (3-7 PM weekdays)
- ✅ Shoulder hours (1-3 PM weekdays)
- ✅ Off-peak hours (all other times)
- ✅ Weekends always off-peak
- ✅ Holidays always off-peak (even during normal peak hours)

### PDF Parsing (`test_tariff_manager.py`)
- ✅ TOU rate extraction from PDF text
- ✅ TOU schedule extraction (peak, shoulder, off-peak times)
- ✅ Fixed charge extraction
- ✅ Holiday list extraction from PDF

### Sensors (`test_sensor.py`)
- ✅ Current rate sensor with proper units ($/kWh or $/therm)
- ✅ TOU rate sensors (peak, shoulder, off-peak)
- ✅ TOU period sensor showing current period
- ✅ Fixed charge sensor
- ✅ Holiday status in sensor attributes

### Configuration (`test_config_flow_simple.py`)
- ✅ Valid state/service combinations
- ✅ Invalid state rejection
- ✅ Service availability validation

### Integration (`test_integration.py`)
- ✅ Complete TOU scenario through 24-hour cycle
- ✅ Correct rate changes based on time of day
- ✅ PDF parsing full cycle

## Running Tests

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_tariff_manager.py -v  # Core logic tests
pytest tests/test_sensor.py -v          # Sensor tests
pytest tests/test_integration.py -v     # Integration tests

# Run with coverage
pytest tests/ -v --cov=custom_components.xcel_energy_tariff
```

## Key Test Scenarios

### Holiday + Peak Time
The tests verify that holidays override peak periods. For example:
- July 4th at 4 PM (normally peak) → Off-Peak
- Christmas Day at 3 PM (normally peak) → Off-Peak

### Time Transitions
Tests verify correct period transitions:
- 12:59 PM weekday → Off-Peak
- 1:00 PM weekday → Shoulder
- 3:00 PM weekday → Peak
- 7:00 PM weekday → Off-Peak

### Weekend Override
Tests confirm weekends are always off-peak:
- Saturday 4 PM → Off-Peak (would be peak on weekday)
- Sunday 2 PM → Off-Peak (would be shoulder on weekday)