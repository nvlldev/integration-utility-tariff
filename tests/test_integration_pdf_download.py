"""Integration test for PDF download from sources.json and sensor data creation."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime
import logging

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import (
    XcelEnergyProvider,
    XcelEnergyPDFExtractor
)
from custom_components.utility_tariff.coordinator import UtilityTariffCoordinator

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_pdf_download_from_sources_json():
    """Test that PDF is downloaded from URL specified in sources.json."""
    # Load actual sources.json
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    sources_file = component_dir / "sources.json"
    
    with open(sources_file, 'r') as f:
        sources_data = json.load(f)
    
    # Get the Xcel Energy electric source
    xcel_sources = sources_data.get("providers", {}).get("xcel_energy", {}).get("electric", [])
    assert len(xcel_sources) > 0, "No Xcel Energy electric sources found in sources.json"
    
    # Get the first (most recent) source
    latest_source = xcel_sources[0]
    source_url = latest_source["source"]
    
    print(f"\nTesting with source: {source_url}")
    print(f"Effective date: {latest_source['effective_date']}")
    print(f"Description: {latest_source['description']}")
    
    # Create extractor and test download
    extractor = XcelEnergyPDFExtractor()
    
    # Mock aiohttp to simulate successful download
    mock_pdf_content = b"%PDF-1.4\n" + b"Mock PDF content" * 100
    
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_pdf_content)
        
        mock_session.get = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        mock_session_class.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session))
        
        # Test the fetch - should use URL from sources.json
        result = await extractor.fetch_tariff_data(
            url=None,  # No explicit URL, should use sources.json
            service_type="electric",
            rate_schedule="residential",
            use_bundled_fallback=False
        )
        
        # Verify the correct URL was used
        mock_session.get.assert_called_once()
        called_url = mock_session.get.call_args[0][0]
        assert called_url == source_url, f"Expected URL {source_url}, got {called_url}"
        
        print(f"\n✓ Successfully attempted download from: {called_url}")


@pytest.mark.asyncio
async def test_sensor_data_from_downloaded_pdf():
    """Test that sensor data is correctly created from downloaded PDF."""
    # Mock PDF content that looks like actual Xcel data
    mock_pdf_text = """
    Colorado Public Utilities Commission Schedule No. 8
    
    Residential Service Schedule R
    
    Total Monthly Rate Summary
    
    Service & Facility Charge: $8.17
    
    Winter Energy Charge per kWh: $0.14295
    Summer Energy Charge per kWh: $0.15952
    
    Time of Use Rates:
    Winter Peak (3pm-7pm weekdays): $0.29871
    Winter Shoulder: $0.14295
    Winter Off-Peak: $0.10517
    
    Summer Peak (3pm-7pm weekdays): $0.31624
    Summer Shoulder: $0.15952
    Summer Off-Peak: $0.12174
    """
    
    # Create provider
    provider = XcelEnergyProvider()
    
    # Mock the PDF download and parsing
    with patch.object(XcelEnergyPDFExtractor, 'fetch_tariff_data') as mock_fetch:
        mock_fetch.return_value = {
            "rates": {"winter": 0.14295, "summer": 0.15952},
            "tou_rates": {
                "winter_peak": 0.29871,
                "winter_shoulder": 0.14295,
                "winter_off_peak": 0.10517,
                "summer_peak": 0.31624,
                "summer_shoulder": 0.15952,
                "summer_off_peak": 0.12174
            },
            "fixed_charges": {"service_charge": 8.17},
            "data_source": "Xcel Energy PDF",
            "pdf_source": "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf",
            "metadata": {
                "rate_schedule": "Residential (R)",
                "effective_date": "2025-04-01",
                "tariff_name": "Electric Rate Summary - April 2025"
            }
        }
        
        # Get tariff data
        tariff_data = await provider.get_tariff_data(
            service_type="electric",
            rate_schedule="residential",
            config={}
        )
        
        # Verify the data structure
        assert tariff_data is not None, "Tariff data should not be None"
        assert "rates" in tariff_data, "Tariff data should contain rates"
        assert "tou_rates" in tariff_data, "Tariff data should contain TOU rates"
        assert "fixed_charges" in tariff_data, "Tariff data should contain fixed charges"
        
        # Verify rate values
        assert tariff_data["rates"]["winter"] == 0.14295
        assert tariff_data["rates"]["summer"] == 0.15952
        
        # Verify TOU rates
        assert tariff_data["tou_rates"]["winter_peak"] == 0.29871
        assert tariff_data["tou_rates"]["summer_peak"] == 0.31624
        
        # Verify fixed charges
        assert tariff_data["fixed_charges"]["service_charge"] == 8.17
        
        # Verify metadata
        assert tariff_data["data_source"] == "Xcel Energy PDF"
        assert "pdf_source" in tariff_data
        
        print("\n✓ Successfully created sensor data from PDF")
        print(f"  - Winter rate: ${tariff_data['rates']['winter']}/kWh")
        print(f"  - Summer rate: ${tariff_data['rates']['summer']}/kWh")
        print(f"  - Service charge: ${tariff_data['fixed_charges']['service_charge']}/month")


@pytest.mark.asyncio
async def test_coordinator_with_pdf_source():
    """Test that coordinator properly uses PDF data from sources.json."""
    # Mock Home Assistant
    mock_hass = Mock()
    mock_hass.data = {}
    
    # Create mock config entry
    mock_config_entry = Mock()
    mock_config_entry.data = {
        "provider": "xcel_energy",
        "service_type": "electric",
        "rate_schedule": "residential",
        "name": "Xcel Energy Electric"
    }
    mock_config_entry.entry_id = "test_entry_id"
    
    # Create coordinator
    coordinator = UtilityTariffCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry
    )
    
    # Mock the provider's get_tariff_data method
    with patch.object(XcelEnergyProvider, 'get_tariff_data') as mock_get_data:
        mock_get_data.return_value = {
            "rates": {"winter": 0.14295, "summer": 0.15952},
            "tou_rates": {
                "winter_peak": 0.29871,
                "winter_shoulder": 0.14295,
                "winter_off_peak": 0.10517,
                "summer_peak": 0.31624,
                "summer_shoulder": 0.15952,
                "summer_off_peak": 0.12174
            },
            "fixed_charges": {"service_charge": 8.17},
            "data_source": "Xcel Energy PDF",
            "pdf_source": "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf",
            "metadata": {
                "rate_schedule": "Residential (R)",
                "effective_date": "2025-04-01"
            }
        }
        
        # Update coordinator data
        await coordinator._async_update_data()
        
        # Verify coordinator has the data
        assert coordinator.data is not None
        assert "rates" in coordinator.data
        assert coordinator.data["rates"]["winter"] == 0.14295
        assert coordinator.data["data_source"] == "Xcel Energy PDF"
        
        print("\n✓ Coordinator successfully loaded PDF data")
        print(f"  - Data source: {coordinator.data['data_source']}")
        print(f"  - PDF source: {coordinator.data.get('pdf_source', 'N/A')}")


@pytest.mark.asyncio 
async def test_pdf_download_fallback():
    """Test fallback behavior when PDF download fails."""
    extractor = XcelEnergyPDFExtractor()
    
    # Mock failed download
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        mock_session_class.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session))
        
        # Mock bundled PDF fallback
        with patch.object(extractor, '_get_bundled_pdf') as mock_bundled:
            mock_bundled.return_value = (
                {"filename": "xcel_electric_2024.pdf", "version": "bundled"},
                b"%PDF-1.4\nBundled PDF content"
            )
            
            # Should fall back to bundled PDF
            result = await extractor.fetch_tariff_data(
                url=None,
                service_type="electric", 
                rate_schedule="residential",
                use_bundled_fallback=True
            )
            
            # Verify fallback was used
            mock_bundled.assert_called_once_with("electric")
            
            print("\n✓ Successfully fell back to bundled PDF when download failed")


@pytest.mark.asyncio
async def test_real_pdf_parsing():
    """Test parsing of actual PDF content structure."""
    # This tests the actual parsing logic with a mock PDF
    extractor = XcelEnergyPDFExtractor()
    
    # Mock PDF download with realistic content
    mock_pdf_content = b"%PDF-1.4\n"  # Minimal valid PDF header
    
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_pdf_content)
        
        mock_session.get = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        mock_session_class.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session))
        
        # Mock PyPDF2 reader
        with patch('PyPDF2.PdfReader') as mock_pdf_reader:
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = """
                Residential ( R) 
                Service & Facility $8.17
                Winter Energy per kWh $0.14295
                Summer Energy per kWh $0.15952
                
                Time of Use
                Winter Peak per kWh $0.29871
                Winter Shoulder per kWh $0.14295
                Winter Off-Peak per kWh $0.10517
                Summer Peak per kWh $0.31624
                Summer Shoulder per kWh $0.15952
                Summer Off-Peak per kWh $0.12174
            """
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            
            # Test extraction
            result = await extractor.fetch_tariff_data(
                url="https://example.com/test.pdf",
                service_type="electric",
                rate_schedule="residential"
            )
            
            # Verify extraction worked
            assert result is not None
            assert "rates" in result
            assert result["rates"]["winter"] == 0.14295
            assert result["rates"]["summer"] == 0.15952
            assert result["tou_rates"]["winter_peak"] == 0.29871
            assert result["fixed_charges"]["service_charge"] == 8.17
            
            print("\n✓ Successfully parsed PDF content into sensor data")
            print(f"  - Extracted {len(result['rates'])} standard rates")
            print(f"  - Extracted {len(result['tou_rates'])} TOU rates")
            print(f"  - Extracted {len(result['fixed_charges'])} fixed charges")


if __name__ == "__main__":
    # Run all tests
    print("=== Running Integration Tests for PDF Download ===\n")
    
    asyncio.run(test_pdf_download_from_sources_json())
    asyncio.run(test_sensor_data_from_downloaded_pdf())
    asyncio.run(test_coordinator_with_pdf_source())
    asyncio.run(test_pdf_download_fallback())
    asyncio.run(test_real_pdf_parsing())
    
    print("\n✓ All integration tests passed!")