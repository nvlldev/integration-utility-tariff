"""Test Xcel Energy rate summary PDF functionality."""
import asyncio
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import (
    XcelEnergyDataSource,
    XcelEnergyProvider,
)


async def test_rate_summary_urls():
    """Test that rate summary URLs are configured correctly."""
    data_source = XcelEnergyDataSource()
    
    # Test Colorado electric configuration
    config = data_source.get_source_config("CO", "electric", "residential_tou")
    print(f"Colorado Electric URL: {config['url']}")
    print(f"Type: {config['type']}")
    print(f"Note: {config.get('note', 'N/A')}")
    
    # Test if the URL is accessible
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(config['url'], allow_redirects=True) as response:
                print(f"\nURL Status: {response.status}")
                if response.status == 200:
                    print("✓ Rate summary PDF is accessible!")
                    print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                    print(f"Size: {response.headers.get('Content-Length', 'Unknown')} bytes")
                else:
                    print(f"✗ Unable to access PDF (Status: {response.status})")
        except Exception as e:
            print(f"✗ Error accessing URL: {e}")
    
    # Check fallback rates
    print("\n\nFallback Rates Configuration:")
    fallback = data_source.get_fallback_rates("CO", "electric")
    if fallback:
        print(f"Effective Date: {fallback.get('effective_date', 'Unknown')}")
        print(f"Has base rates: {'rates' in fallback}")
        print(f"Has TOU rates: {'tou_rates' in fallback}")
        print(f"Has fixed charges: {'fixed_charges' in fallback}")
        if 'note' in fallback:
            print(f"Note: {fallback['note']}")


async def test_provider_capabilities():
    """Test provider capabilities and configuration."""
    provider = XcelEnergyProvider()
    
    print("\n\nProvider Information:")
    print(f"Name: {provider.name}")
    print(f"Short Name: {provider.short_name}")
    print(f"Provider ID: {provider.provider_id}")
    
    print(f"\nSupported States (Electric): {provider.supported_states['electric']}")
    print(f"Supported Rate Schedules: {provider.supported_rate_schedules['electric']}")
    print(f"Capabilities: {provider.capabilities}")
    
    # Check data source configuration
    data_source = provider._create_data_source()
    print(f"\nData Source Type: {data_source.__class__.__name__}")
    print(f"Supports Real-time: {data_source.supports_real_time_rates()}")
    print(f"Update Interval: {data_source.get_update_interval()}")


if __name__ == "__main__":
    print("=== Testing Xcel Energy Rate Summary Configuration ===")
    asyncio.run(test_rate_summary_urls())
    asyncio.run(test_provider_capabilities())