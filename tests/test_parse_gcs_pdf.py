"""Test parsing PDF from Google Cloud Storage."""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyPDFExtractor


async def test_parse_gcs_pdf():
    """Test parsing the PDF from Google Cloud Storage."""
    url = "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf"
    
    print("Testing Xcel Energy PDF parsing from Google Cloud Storage")
    print("=" * 60)
    print(f"URL: {url}\n")
    
    extractor = XcelEnergyPDFExtractor()
    
    try:
        # Fetch and parse the PDF
        print("Fetching and parsing PDF...")
        result = await extractor.fetch_tariff_data(
            url=url,
            service_type="electric",
            rate_schedule="residential_tou",
            use_bundled_fallback=False  # Force URL download
        )
        
        print("\n✓ Successfully parsed PDF!")
        print("\nExtracted Data:")
        print("-" * 40)
        
        # Show what was extracted
        if result.get("rates"):
            print("\nBase Rates:")
            for rate_type, value in result["rates"].items():
                print(f"  {rate_type}: ${value:.5f}/kWh")
        
        if result.get("tou_rates"):
            print("\nTime-of-Use Rates:")
            tou = result["tou_rates"]
            for season, rates in tou.items():
                if isinstance(rates, dict):
                    print(f"  {season.title()}:")
                    for period, rate in rates.items():
                        print(f"    {period}: ${rate:.5f}/kWh")
        
        if result.get("fixed_charges"):
            print("\nFixed Charges:")
            for charge_type, value in result["fixed_charges"].items():
                print(f"  {charge_type}: ${value:.2f}")
        
        if result.get("tou_schedule"):
            print("\nTOU Schedule:")
            for period, info in result["tou_schedule"].items():
                print(f"  {period}: {info}")
        
        if result.get("effective_date"):
            print(f"\nEffective Date: {result['effective_date']}")
        
        if result.get("season_definitions"):
            print(f"\nSeason Definitions: {result['season_definitions']}")
        
        # Show metadata
        print(f"\nData Source: {result.get('data_source', 'unknown')}")
        print(f"PDF Source: {result.get('pdf_source', 'unknown')}")
        print(f"PDF URL: {result.get('pdf_url', 'unknown')}")
        
        # Validate the data
        is_valid, error_msg = await extractor.validate_data(result)
        print(f"\nValidation: {'✓ Passed' if is_valid else f'✗ Failed - {error_msg}'}")
        
    except Exception as e:
        print(f"\n✗ Error parsing PDF: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def test_with_different_schedules():
    """Test parsing with different rate schedules."""
    url = "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf"
    extractor = XcelEnergyPDFExtractor()
    
    print("\n\n" + "=" * 60)
    print("Testing different rate schedules")
    print("=" * 60)
    
    schedules = ["residential", "residential_tou", "commercial"]
    
    for schedule in schedules:
        print(f"\n\nTesting {schedule}:")
        print("-" * 40)
        
        try:
            result = await extractor.fetch_tariff_data(
                url=url,
                service_type="electric",
                rate_schedule=schedule,
                use_bundled_fallback=False
            )
            
            if result.get("rates"):
                rates = result["rates"]
                print(f"Found {len(rates)} rate(s)")
                # Show first few rates
                for i, (rate_type, value) in enumerate(rates.items()):
                    if i < 3:  # Show first 3
                        print(f"  {rate_type}: ${value:.5f}/kWh")
            else:
                print("No rates found")
                
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_parse_gcs_pdf())
    asyncio.run(test_with_different_schedules())