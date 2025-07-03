"""Test actual PDF download from sources.json URLs."""
import asyncio
import json
import aiohttp
from pathlib import Path
from io import BytesIO
import PyPDF2
import logging

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyPDFExtractor

# Set up logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def test_real_pdf_download():
    """Test downloading and parsing the actual PDF from sources.json."""
    # Load sources.json
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    sources_file = component_dir / "sources.json"
    
    with open(sources_file, 'r') as f:
        sources_data = json.load(f)
    
    # Get the Xcel Energy electric source URL
    xcel_sources = sources_data.get("providers", {}).get("xcel_energy", {}).get("electric", [])
    if not xcel_sources:
        print("No Xcel Energy electric sources found in sources.json")
        return
    
    source_url = xcel_sources[0]["source"]
    print(f"Testing with real URL: {source_url}")
    print(f"Effective date: {xcel_sources[0]['effective_date']}")
    
    # Download the PDF
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url) as response:
                if response.status == 200:
                    pdf_content = await response.read()
                    print(f"\n✓ Successfully downloaded PDF ({len(pdf_content):,} bytes)")
                    
                    # Try to parse it
                    pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
                    print(f"✓ PDF has {len(pdf_reader.pages)} pages")
                    
                    # Extract text from first page
                    first_page_text = pdf_reader.pages[0].extract_text()
                    print(f"✓ Extracted {len(first_page_text)} characters from first page")
                    
                    # Look for key rate information
                    if "Residential" in first_page_text:
                        print("✓ Found 'Residential' in PDF")
                    if "kWh" in first_page_text:
                        print("✓ Found 'kWh' in PDF")
                    if "$" in first_page_text:
                        print("✓ Found '$' in PDF")
                    
                    # Save a copy for inspection
                    test_pdf_path = Path(__file__).parent / "downloaded_test.pdf"
                    with open(test_pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    print(f"\n✓ Saved PDF copy to: {test_pdf_path}")
                    
                else:
                    print(f"✗ Failed to download: HTTP {response.status}")
                    
    except Exception as e:
        print(f"✗ Error downloading PDF: {e}")


async def test_full_extraction_from_url():
    """Test the full extraction process using the real URL."""
    extractor = XcelEnergyPDFExtractor()
    
    try:
        # Test without explicit URL - should use sources.json
        result = await extractor.fetch_tariff_data(
            url=None,
            service_type="electric",
            rate_schedule="residential",
            use_bundled_fallback=True
        )
        
        if result:
            print("\n✓ Successfully extracted data from PDF")
            print(f"  Data source: {result.get('data_source', 'Unknown')}")
            print(f"  PDF source: {result.get('pdf_source', 'Unknown')}")
            
            if 'rates' in result:
                print(f"\n  Standard Rates:")
                for season, rate in result['rates'].items():
                    print(f"    - {season}: ${rate}/kWh")
            
            if 'tou_rates' in result:
                print(f"\n  Time-of-Use Rates:")
                for period, rate in result['tou_rates'].items():
                    print(f"    - {period}: ${rate}/kWh")
            
            if 'fixed_charges' in result:
                print(f"\n  Fixed Charges:")
                for charge, amount in result['fixed_charges'].items():
                    print(f"    - {charge}: ${amount}")
            
            if 'metadata' in result:
                print(f"\n  Metadata:")
                for key, value in result['metadata'].items():
                    print(f"    - {key}: {value}")
        else:
            print("\n✗ Failed to extract data from PDF")
            
    except Exception as e:
        print(f"\n✗ Error during extraction: {e}")
        import traceback
        traceback.print_exc()


async def test_sensor_values():
    """Test that sensor values match expected format."""
    extractor = XcelEnergyPDFExtractor()
    
    try:
        result = await extractor.fetch_tariff_data(
            url=None,
            service_type="electric", 
            rate_schedule="residential",
            use_bundled_fallback=True
        )
        
        if result and 'rates' in result:
            # Verify rate values are reasonable
            winter_rate = result['rates'].get('winter', 0)
            summer_rate = result['rates'].get('summer', 0)
            
            print("\n=== Sensor Value Validation ===")
            
            # Check winter rate
            if 0.05 <= winter_rate <= 0.50:
                print(f"✓ Winter rate ${winter_rate}/kWh is in reasonable range")
            else:
                print(f"⚠ Winter rate ${winter_rate}/kWh seems unusual")
            
            # Check summer rate  
            if 0.05 <= summer_rate <= 0.50:
                print(f"✓ Summer rate ${summer_rate}/kWh is in reasonable range")
            else:
                print(f"⚠ Summer rate ${summer_rate}/kWh seems unusual")
            
            # Check summer > winter (typical pattern)
            if summer_rate > winter_rate:
                print(f"✓ Summer rate is higher than winter rate (expected)")
            else:
                print(f"⚠ Summer rate is not higher than winter rate")
            
            # Check TOU rates if available
            if 'tou_rates' in result:
                peak_rates = [v for k, v in result['tou_rates'].items() if 'peak' in k and 'off' not in k]
                off_peak_rates = [v for k, v in result['tou_rates'].items() if 'off_peak' in k]
                
                if peak_rates and off_peak_rates:
                    max_peak = max(peak_rates)
                    min_off_peak = min(off_peak_rates)
                    
                    if max_peak > min_off_peak:
                        print(f"✓ Peak rates (${max_peak}) are higher than off-peak rates (${min_off_peak})")
                    else:
                        print(f"⚠ Peak rates are not higher than off-peak rates")
            
            # Check service charge
            if 'fixed_charges' in result:
                service_charge = result['fixed_charges'].get('service_charge', 0)
                if 5 <= service_charge <= 20:
                    print(f"✓ Service charge ${service_charge}/month is in reasonable range")
                else:
                    print(f"⚠ Service charge ${service_charge}/month seems unusual")
                    
    except Exception as e:
        print(f"\n✗ Error validating sensor values: {e}")


if __name__ == "__main__":
    print("=== Testing Real PDF Download and Parsing ===\n")
    
    # Run the tests
    asyncio.run(test_real_pdf_download())
    asyncio.run(test_full_extraction_from_url())
    asyncio.run(test_sensor_values())
    
    print("\n✓ Real PDF tests completed!")