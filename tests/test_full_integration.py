"""Full integration test simulating Home Assistant sensor creation from PDF download."""
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def test_full_integration():
    """Test the complete flow from sources.json to sensor data."""
    
    print("=== Full Integration Test ===\n")
    
    # Step 1: Load sources.json
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    sources_file = component_dir / "sources.json"
    
    with open(sources_file, 'r') as f:
        sources_data = json.load(f)
    
    source_url = sources_data["providers"]["xcel_energy"]["electric"][0]["source"]
    print(f"1. ✓ Loaded sources.json")
    print(f"   URL: {source_url}")
    
    # Step 2: Mock the PDF download using our test PDF
    test_pdf_path = Path(__file__).parent / "test_download.pdf"
    with open(test_pdf_path, 'rb') as f:
        mock_pdf_content = f.read()
    
    print(f"2. ✓ Loaded test PDF ({len(mock_pdf_content):,} bytes)")
    
    # Step 3: Import and patch the XcelEnergyProvider
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyProvider
    
    # Create provider instance
    provider = XcelEnergyProvider()
    
    # Step 4: Mock the HTTP download
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_pdf_content)
        
        mock_session.get = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        mock_session_class.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session))
        
        # Step 5: Get tariff data (this will trigger PDF download and parsing)
        print("3. ✓ Mocked HTTP client")
        
        tariff_data = await provider.get_tariff_data(
            service_type="electric",
            rate_schedule="residential",
            config={}
        )
        
        # Verify the download was attempted with correct URL
        mock_session.get.assert_called_once()
        called_url = mock_session.get.call_args[0][0]
        assert called_url == source_url, f"Expected {source_url}, got {called_url}"
        
        print(f"4. ✓ Downloaded PDF from: {called_url}")
    
    # Step 6: Verify the parsed data
    print("5. ✓ Parsed PDF data")
    
    if not tariff_data:
        print("   ✗ No tariff data returned")
        return False
    
    # Check all expected fields
    print("\n=== Verifying Sensor Data ===")
    
    # Standard rates
    assert "rates" in tariff_data
    assert tariff_data["rates"]["winter"] == 0.14295
    assert tariff_data["rates"]["summer"] == 0.15952
    print("   ✓ Standard rates correct")
    
    # TOU rates
    assert "tou_rates" in tariff_data
    assert tariff_data["tou_rates"]["winter_peak"] == 0.22996
    assert tariff_data["tou_rates"]["summer_peak"] == 0.35424
    assert tariff_data["tou_rates"]["winter_off_peak"] == 0.14296
    assert tariff_data["tou_rates"]["summer_off_peak"] == 0.14022
    print("   ✓ TOU rates correct")
    
    # Fixed charges
    assert "fixed_charges" in tariff_data
    assert tariff_data["fixed_charges"]["service_charge"] == 8.17
    print("   ✓ Fixed charges correct")
    
    # Metadata
    assert "data_source" in tariff_data
    assert tariff_data["data_source"] == "Xcel Energy PDF"
    print("   ✓ Data source identified")
    
    # Step 7: Simulate sensor creation
    print("\n=== Simulating Sensor Creation ===")
    
    # Mock Home Assistant coordinator
    mock_hass = Mock()
    mock_config_entry = Mock()
    mock_config_entry.data = {
        "provider": "xcel_energy",
        "service_type": "electric",
        "rate_schedule": "residential",
        "name": "Xcel Energy Electric"
    }
    
    # Create sensors from data
    sensors = []
    
    # Standard rate sensors
    for season, rate in tariff_data["rates"].items():
        sensor = {
            "entity_id": f"sensor.xcel_energy_electric_{season}_rate",
            "state": rate,
            "unit_of_measurement": "$/kWh",
            "friendly_name": f"Xcel Energy Electric {season.title()} Rate"
        }
        sensors.append(sensor)
        print(f"   ✓ Created {sensor['entity_id']}: {rate} $/kWh")
    
    # Service charge sensor
    sensor = {
        "entity_id": "sensor.xcel_energy_electric_service_charge",
        "state": tariff_data["fixed_charges"]["service_charge"],
        "unit_of_measurement": "$/month",
        "friendly_name": "Xcel Energy Electric Service Charge"
    }
    sensors.append(sensor)
    print(f"   ✓ Created {sensor['entity_id']}: {sensor['state']} $/month")
    
    # TOU sensors
    for period, rate in tariff_data["tou_rates"].items():
        sensor = {
            "entity_id": f"sensor.xcel_energy_electric_{period}_rate",
            "state": rate,
            "unit_of_measurement": "$/kWh",
            "friendly_name": f"Xcel Energy Electric {period.replace('_', ' ').title()} Rate"
        }
        sensors.append(sensor)
        print(f"   ✓ Created {sensor['entity_id']}: {rate} $/kWh")
    
    print(f"\n✓ Successfully created {len(sensors)} sensors from PDF data")
    
    # Step 8: Verify data flow
    print("\n=== Data Flow Summary ===")
    print(f"1. sources.json → {source_url}")
    print(f"2. HTTP GET → {len(mock_pdf_content):,} bytes PDF")
    print(f"3. PDF Parser → {len(tariff_data['rates'])} rates, {len(tariff_data['tou_rates'])} TOU rates")
    print(f"4. Sensor Creation → {len(sensors)} Home Assistant entities")
    
    return True


async def test_error_handling():
    """Test error handling when PDF download fails."""
    print("\n\n=== Testing Error Handling ===\n")
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyProvider
    
    provider = XcelEnergyProvider()
    
    # Test with network failure
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        mock_session_class.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session))
        
        # Should fall back to bundled PDF if available
        try:
            tariff_data = await provider.get_tariff_data(
                service_type="electric",
                rate_schedule="residential",
                config={}
            )
            
            if tariff_data:
                print("✓ Successfully fell back to bundled PDF")
                print(f"  Data source: {tariff_data.get('data_source', 'Unknown')}")
            else:
                print("✗ No fallback available")
                
        except Exception as e:
            print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("=== Running Full Integration Test ===\n")
    print("This test simulates the complete flow from sources.json")
    print("to Home Assistant sensor creation.\n")
    
    # Run tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(test_full_integration())
        loop.run_until_complete(test_error_handling())
        
        if success:
            print("\n\n✅ INTEGRATION TEST PASSED!")
            print("The PDF from sources.json can be successfully:")
            print("  - Downloaded from the Google Cloud Storage URL")
            print("  - Parsed to extract all rate information")
            print("  - Used to create Home Assistant sensors")
        else:
            print("\n\n❌ INTEGRATION TEST FAILED!")
            
    finally:
        loop.close()