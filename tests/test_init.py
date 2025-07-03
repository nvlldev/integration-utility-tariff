"""Test the Utility Tariff integration setup."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.utility_tariff import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.utility_tariff.const import DOMAIN


class MockConfigEntry:
    """Mock config entry."""

    def __init__(self, domain, data):
        """Initialize."""
        self.domain = domain
        self.data = data
        self.entry_id = "test_entry_id"
        self.unique_id = "test_unique_id"
        self.title = data.get("name", "Test")
        self.state = ConfigEntryState.NOT_LOADED
        self.runtime_data = None

    async def async_setup(self, hass):
        """Mock setup."""
        self.state = ConfigEntryState.LOADED
        return True


@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
    # Mock coordinator
    with patch(
        "custom_components.utility_tariff.UtilityTariffCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        # Setup entry
        result = await async_setup_entry(hass, config_entry)
        
        assert result is True
        assert config_entry.runtime_data is not None
        assert config_entry.runtime_data == mock_coordinator
        
        # Verify coordinator was initialized
        mock_coordinator_class.assert_called_once_with(hass, config_entry)
        mock_coordinator.async_config_entry_first_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_setup_entry_with_pdf_download(hass: HomeAssistant) -> None:
    """Test setup downloads PDF from sources.json."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
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
                Service and Facility per Month 8.17
                Winter Energy per kWh 0.14295
                Summer Energy per kWh 0.15952
            """
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            
            # Setup entry
            result = await async_setup_entry(hass, config_entry)
            
            assert result is True
            
            # Verify PDF was downloaded
            assert mock_session.get.called
            called_url = mock_session.get.call_args[0][0]
            assert "storage.googleapis.com" in called_url
            assert "all-rates-04-01-2025.pdf" in called_url


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Test",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    
    # Mock coordinator
    mock_coordinator = AsyncMock()
    config_entry.runtime_data = mock_coordinator
    
    # Mock platforms
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms"
    ) as mock_unload:
        mock_unload.return_value = True
        
        result = await async_unload_entry(hass, config_entry)
        
        assert result is True
        assert config_entry.runtime_data is None


@pytest.mark.asyncio
async def test_setup_entry_failure(hass: HomeAssistant) -> None:
    """Test setup failure raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Test",
            "provider": "xcel_energy",
            "service_type": "electric", 
            "rate_schedule": "residential",
        },
    )
    
    # Mock coordinator with failure
    with patch(
        "custom_components.utility_tariff.UtilityTariffCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Failed to fetch data")
        )
        mock_coordinator_class.return_value = mock_coordinator
        
        # Should raise ConfigEntryNotReady
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)
        
        assert "Failed to fetch data" in str(exc_info.value)