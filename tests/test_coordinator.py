"""Test the Utility Tariff coordinator."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.utility_tariff.const import DOMAIN
from custom_components.utility_tariff.coordinator import UtilityTariffCoordinator


class MockConfigEntry:
    """Mock config entry."""

    def __init__(self, domain, data):
        """Initialize."""
        self.domain = domain
        self.data = data
        self.entry_id = "test_entry_id"
        self.unique_id = "test_unique_id"
        self.title = data.get("name", "Test")


@pytest.mark.asyncio
async def test_coordinator_update_with_pdf_download(hass: HomeAssistant) -> None:
    """Test coordinator update with PDF download from sources.json."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
    # Create coordinator
    coordinator = UtilityTariffCoordinator(hass, config_entry)
    
    # Mock PDF content
    mock_pdf_content = b"%PDF-1.4\nMock PDF content"
    
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_pdf_content)
        
        mock_session.get = AsyncMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session)
        )
        
        # Mock PDF parsing
        with patch("PyPDF2.PdfReader") as mock_pdf_reader:
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = """
                Residential ( R)
                Service and Facility per Month 7.10 - 0.81 0.25708 8.17
                Winter Energy per kWh 0.08570 - - 0.00335 0.00940 0.03113 0.00768 - 0.00119 - 0.00450 0.14295
                Summer Energy per kWh 0.10380 - - 0.00335 0.00940 0.03113 0.00768 - 0.00119 (0.00205) 0.00502 0.15952
            """
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            
            # Update coordinator
            await coordinator.async_config_entry_first_refresh()
            
            # Verify PDF was downloaded from correct URL
            assert mock_session.get.called
            called_url = mock_session.get.call_args[0][0]
            assert "storage.googleapis.com" in called_url
            
            # Verify data was extracted
            assert coordinator.data is not None
            assert "rates" in coordinator.data
            assert coordinator.data["rates"]["winter"] == 0.14295
            assert coordinator.data["rates"]["summer"] == 0.15952
            assert coordinator.data["data_source"] == "Xcel Energy PDF"


@pytest.mark.asyncio
async def test_coordinator_update_failure_with_fallback(hass: HomeAssistant) -> None:
    """Test coordinator handles download failure with fallback."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric", 
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
    coordinator = UtilityTariffCoordinator(hass, config_entry)
    
    # Mock failed download
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        mock_session_class.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session)
        )
        
        # Mock bundled PDF fallback
        with patch.object(
            coordinator.provider._extractor, "_get_bundled_pdf"
        ) as mock_bundled:
            mock_bundled.return_value = (
                {"filename": "bundled.pdf", "version": "2024-01"},
                b"%PDF-1.4\nBundled content",
            )
            
            # Mock parsing of bundled PDF
            with patch("PyPDF2.PdfReader") as mock_pdf_reader:
                mock_reader = Mock()
                mock_page = Mock()
                mock_page.extract_text.return_value = """
                    Standard Residential Service
                    Monthly Service Charge: $8.17
                    Winter Rate: $0.14295/kWh
                    Summer Rate: $0.15952/kWh
                """
                mock_reader.pages = [mock_page]
                mock_pdf_reader.return_value = mock_reader
                
                # Should use bundled fallback
                await coordinator.async_config_entry_first_refresh()
                
                # Verify bundled PDF was used
                mock_bundled.assert_called()
                assert coordinator.data is not None
                assert coordinator.data["data_source"] == "Xcel Energy PDF (Bundled)"


@pytest.mark.asyncio
async def test_coordinator_sensor_data_structure(hass: HomeAssistant) -> None:
    """Test coordinator provides correct data structure for sensors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential_tou",
        },
    )
    
    coordinator = UtilityTariffCoordinator(hass, config_entry)
    
    # Mock complete tariff data
    mock_tariff_data = {
        "rates": {"winter": 0.14295, "summer": 0.15952},
        "tou_rates": {
            "winter_peak": 0.22996,
            "winter_shoulder": 0.18646,
            "winter_off_peak": 0.14296,
            "summer_peak": 0.35424,
            "summer_shoulder": 0.24860,
            "summer_off_peak": 0.14022,
        },
        "fixed_charges": {"service_charge": 8.17},
        "data_source": "Xcel Energy PDF",
        "pdf_source": "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf",
        "metadata": {
            "rate_schedule": "Residential (R)",
            "effective_date": "2025-04-01",
            "tariff_name": "Electric Rate Summary - April 2025",
        },
    }
    
    with patch.object(
        coordinator.provider, "get_tariff_data", return_value=mock_tariff_data
    ):
        await coordinator.async_config_entry_first_refresh()
        
        # Verify all required data for sensors
        assert coordinator.data is not None
        
        # Standard rates
        assert "rates" in coordinator.data
        assert len(coordinator.data["rates"]) == 2
        
        # TOU rates
        assert "tou_rates" in coordinator.data
        assert len(coordinator.data["tou_rates"]) == 6
        
        # Fixed charges
        assert "fixed_charges" in coordinator.data
        assert "service_charge" in coordinator.data["fixed_charges"]
        
        # Metadata
        assert "data_source" in coordinator.data
        assert "pdf_source" in coordinator.data
        assert "metadata" in coordinator.data
        
        # All values should be numeric for sensor creation
        for rate in coordinator.data["rates"].values():
            assert isinstance(rate, (int, float))
        
        for rate in coordinator.data["tou_rates"].values():
            assert isinstance(rate, (int, float))
        
        for charge in coordinator.data["fixed_charges"].values():
            assert isinstance(charge, (int, float))


@pytest.mark.asyncio
async def test_coordinator_update_interval(hass: HomeAssistant) -> None:
    """Test coordinator update interval."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Test",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
    coordinator = UtilityTariffCoordinator(hass, config_entry)
    
    # Check update interval is set correctly
    assert coordinator.update_interval == timedelta(hours=24)