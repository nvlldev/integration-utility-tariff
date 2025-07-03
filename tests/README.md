# Utility Tariff Integration Tests

This directory contains comprehensive tests for the Utility Tariff Home Assistant integration, including tests for PDF download from sources.json and sensor data creation.

## Test Coverage

### PDF Download and Parsing (`test_sensor.py`, `test_integration_*.py`)
- ✅ PDF download from Google Cloud Storage URLs in sources.json
- ✅ Parsing of new summary table format (April 2025)
- ✅ Extraction of standard rates (winter/summer)
- ✅ Extraction of TOU rates (6 different periods)
- ✅ Extraction of fixed charges (service charge)
- ✅ Fallback to bundled PDF when download fails

### Integration Tests
- `test_integration_pdf_download.py` - Mock-based integration tests
- `test_full_integration.py` - Complete flow simulation
- `test_integration_summary.py` - Validates end-to-end data flow
- `test_parse_new_format.py` - Tests new PDF format parsing

### Sensors (`test_sensor.py`)
- ✅ Current rate sensor with proper units ($/kWh)
- ✅ Standard rate sensors (winter/summer)
- ✅ TOU rate sensors (peak, shoulder, off-peak for each season)
- ✅ Service charge sensor
- ✅ PDF source tracking in sensor attributes

### Coordinator (`test_coordinator.py`)
- ✅ Data update from PDF sources
- ✅ Fallback behavior on download failure
- ✅ Sensor data structure validation
- ✅ Update interval configuration

### Configuration (`test_config_flow.py`)
- ✅ Valid provider/service combinations
- ✅ Invalid provider rejection
- ✅ Duplicate entry prevention

### Integration Setup (`test_init.py`)
- ✅ Entry setup with PDF download
- ✅ Entry unload
- ✅ Error handling

## Key Test: PDF Download from sources.json

The main integration test in `test_sensor.py` verifies the complete flow:

```python
@pytest.mark.asyncio
async def test_pdf_download_from_sources_integration(hass: HomeAssistant) -> None:
    """Test that PDF is downloaded from sources.json URL and sensors are created."""
```

This test confirms:
1. The Google Cloud Storage URL is read from sources.json
2. The PDF is downloaded successfully
3. All rates are extracted correctly from the Charge Amount column:
   - Winter rate: $0.08570/kWh
   - Summer rate: $0.10380/kWh
   - Service charge: $7.10/month
   - 6 TOU rates for different periods

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run specific test file
pytest tests/test_sensor.py -v

# Run the PDF download integration test
pytest tests/test_sensor.py::test_pdf_download_from_sources_integration -v

# Run with coverage
pytest --cov=custom_components.utility_tariff

# Run integration summary test (no HA dependencies)
python tests/test_integration_summary.py
```

## Test Data

### Downloaded PDF (April 2025)
The test suite includes a PDF downloaded from Google Cloud Storage that contains:
- Summary table format with all rates in a single page
- Multiple columns with the final column containing total rates
- Standard residential rates and Time-of-Use rates
- Service charges and facility fees

### Mocking Strategy
Tests use mocking to:
- Simulate HTTP responses for PDF downloads
- Mock PyPDF2 for consistent PDF parsing
- Provide predictable test data
- Avoid external dependencies in CI/CD

## Expected Sensor Output

When the integration runs with the April 2025 PDF, it creates these sensors (using Charge Amount values):
- `sensor.xcel_energy_electric_winter_rate`: 0.08570 $/kWh
- `sensor.xcel_energy_electric_summer_rate`: 0.10380 $/kWh
- `sensor.xcel_energy_electric_service_charge`: 7.10 $/month
- `sensor.xcel_energy_electric_winter_peak_rate`: 0.13171 $/kWh
- `sensor.xcel_energy_electric_winter_shoulder_rate`: 0.10460 $/kWh
- `sensor.xcel_energy_electric_winter_off_peak_rate`: 0.07749 $/kWh
- `sensor.xcel_energy_electric_summer_peak_rate`: 0.20915 $/kWh
- `sensor.xcel_energy_electric_summer_shoulder_rate`: 0.14332 $/kWh
- `sensor.xcel_energy_electric_summer_off_peak_rate`: 0.07749 $/kWh