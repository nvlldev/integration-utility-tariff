"""Test tariff sources functionality."""
import asyncio
import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyPDFExtractor


async def test_bundled_pdf_loading():
    """Test loading tariff sources with new format."""
    extractor = XcelEnergyPDFExtractor()
    
    print("Testing tariff source loading for Xcel Energy...\n")
    
    # Test electric service
    print("1. Testing electric service:")
    pdf_info, pdf_content = await extractor._get_bundled_pdf("electric")
    if pdf_info:
        print(f"   ✓ Found tariff source: {pdf_info.get('source', pdf_info.get('filename', 'unknown'))}")
        print(f"     Version: {pdf_info.get('version', 'unknown')}")
        print(f"     Effective: {pdf_info.get('effective_date', 'unknown')}")
        print(f"     Source: {pdf_info.get('source_type', 'unknown')} - {pdf_info.get('source', 'unknown')}")
        if pdf_content:
            print(f"     Size: {len(pdf_content):,} bytes")
    else:
        print("   ✗ No tariff source found for electric service")
    
    # Test gas service
    print("\n2. Testing gas service:")
    pdf_info, pdf_content = await extractor._get_bundled_pdf("gas")
    if pdf_info:
        print(f"   ✓ Found tariff source: {pdf_info.get('source', pdf_info.get('filename', 'unknown'))}")
        print(f"     Version: {pdf_info.get('version', 'unknown')}")
        print(f"     Effective: {pdf_info.get('effective_date', 'unknown')}")
        print(f"     Source: {pdf_info.get('source_type', 'unknown')} - {pdf_info.get('source', 'unknown')}")
        if pdf_content:
            print(f"     Size: {len(pdf_content):,} bytes")
    else:
        print("   ✗ No tariff source found for gas service")


async def test_metadata_format():
    """Test the tariff sources metadata format."""
    # Get the path to the component directory
    current_file = Path(__file__)
    component_dir = current_file.parent.parent / "custom_components" / "utility_tariff"
    data_dir = component_dir / "data"
    metadata_file = component_dir / "sources.json"
    
    print("\n\n3. Testing metadata format:")
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        print(f"   Metadata version: {metadata.get('version', '1.0')}")
        
        # Check Xcel Energy entries
        if "providers" in metadata:
            # New format
            xcel_pdfs = metadata.get("providers", {}).get("xcel_energy", {})
        else:
            # Old format
            xcel_pdfs = metadata.get("pdfs", {}).get("xcel_energy", {})
        for service_type, entries in xcel_pdfs.items():
            print(f"\n   {service_type.title()} service:")
            if isinstance(entries, list):
                print(f"   ✓ New format (multiple sources supported)")
                print(f"   Total entries: {len(entries)}")
                # Show first entry
                if entries:
                    first = entries[0]
                    print(f"   Latest: {first.get('version', 'unknown')} - {first.get('effective_date', 'unknown')}")
            else:
                print(f"   ⚠️  Old format (single source)")
    else:
        print("   ✗ No metadata file found")


async def test_pdf_extraction_with_bundled():
    """Test full PDF extraction using tariff sources."""
    extractor = XcelEnergyPDFExtractor()
    
    print("\n\n4. Testing PDF extraction with bundled fallback:")
    
    # Test with no URL (force bundled)
    try:
        result = await extractor.fetch_tariff_data(
            url=None,
            service_type="electric",
            rate_schedule="residential_tou",
            use_bundled_fallback=True
        )
        
        if result:
            print("   ✓ Successfully extracted data from tariff source")
            print(f"     Data source: {result.get('data_source', 'unknown')}")
            print(f"     PDF source: {result.get('pdf_source', 'unknown')}")
            print(f"     Has rates: {'rates' in result}")
            print(f"     Has TOU rates: {'tou_rates' in result}")
            print(f"     Has fixed charges: {'fixed_charges' in result}")
            if result.get('bundled_pdf_info'):
                print(f"     Bundled version: {result['bundled_pdf_info'].get('version', 'unknown')}")
        else:
            print("   ✗ Failed to extract data")
    except Exception as e:
        print(f"   ✗ Error: {e}")


if __name__ == "__main__":
    print("=== Testing Bundled PDF Functionality ===")
    asyncio.run(test_bundled_pdf_loading())
    asyncio.run(test_metadata_format())
    asyncio.run(test_pdf_extraction_with_bundled())