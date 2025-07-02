"""Integration tests for Xcel Energy Tariff."""
import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, AsyncMock, mock_open
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.xcel_energy_tariff import async_setup_entry, async_unload_entry
from custom_components.xcel_energy_tariff.const import DOMAIN


class TestIntegration:
    """Test the full integration setup."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_integration"
        entry.data = {
            "state": "CO",
            "service_type": "electric",
            "rate_schedule": "residential_tou",
        }
        return entry

    @pytest.fixture
    def mock_tariff_data(self):
        """Mock tariff data that would be parsed from PDF."""
        return {
            "last_updated": "2024-01-01T12:00:00",
            "rates": {},
            "tou_rates": {
                "summer": {"peak": 0.13861, "shoulder": 0.09497, "off_peak": 0.05134},
                "winter": {"peak": 0.08727, "shoulder": 0.06930, "off_peak": 0.05134}
            },
            "fixed_charges": {"monthly_service": 5.47},
            "demand_charges": {},
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 P.M. - 7:00 P.M.",
                    "shoulder_hours": "1:00 P.M. - 3:00 P.M.",
                    "off_peak_hours": "All other hours, weekends and holidays",
                    "applies_to": "weekdays except holidays",
                },
                "winter": {
                    "peak_hours": "3:00 P.M. - 7:00 P.M.",
                    "shoulder_hours": "1:00 P.M. - 3:00 P.M.",
                    "off_peak_hours": "All other hours, weekends and holidays",
                    "applies_to": "weekdays except holidays",
                },
                "holidays": [
                    "New Year's Day", "Memorial Day", "Independence Day",
                    "Labor Day", "Thanksgiving Day", "Christmas Day"
                ]
            }
        }

    @patch('custom_components.xcel_energy_tariff.tariff_manager.XcelTariffManager')
    @patch('homeassistant.helpers.update_coordinator.DataUpdateCoordinator')
    async def test_setup_entry(self, mock_coordinator_class, mock_manager_class, hass, mock_config_entry, mock_tariff_data):
        """Test setting up the integration."""
        # Setup mocks
        mock_manager = Mock()
        mock_manager.async_update_tariffs = AsyncMock(return_value=mock_tariff_data)
        mock_manager_class.return_value = mock_manager
        
        mock_coordinator = Mock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.data = mock_tariff_data
        mock_coordinator_class.return_value = mock_coordinator
        
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        
        # Run setup
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is True
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        
        # Verify coordinator was created with correct update method
        mock_coordinator_class.assert_called_once()
        coordinator_kwargs = mock_coordinator_class.call_args.kwargs
        assert coordinator_kwargs["update_method"] == mock_manager.async_update_tariffs
        assert coordinator_kwargs["update_interval"].days == 1
        
        # Verify platforms were set up
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    async def test_unload_entry(self, hass, mock_config_entry):
        """Test unloading the integration."""
        # Setup data
        hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": Mock(),
                    "tariff_manager": Mock(),
                }
            }
        }
        
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        
        # Run unload
        result = await async_unload_entry(hass, mock_config_entry)
        
        assert result is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    @patch('custom_components.xcel_energy_tariff.tariff_manager.dt_util')
    def test_complete_tou_scenario(self, mock_dt_util, mock_tariff_data, tmp_path):
        """Test a complete TOU scenario through the day."""
        from custom_components.xcel_energy_tariff.tariff_manager import XcelTariffManager
        
        # Create manager with test data
        mock_hass = Mock()
        cache_path = tmp_path / "cache"
        cache_path.mkdir()
        mock_hass.config.path.return_value = str(cache_path)
        manager = XcelTariffManager(mock_hass, "CO", "electric", "residential_tou")
        manager._tariff_data = mock_tariff_data
        
        # Test different times of day
        test_cases = [
            # (hour, minute, weekday, expected_period, expected_rate)
            (0, 0, 1, "Off-Peak", 0.05134),      # Midnight Tuesday
            (12, 0, 1, "Off-Peak", 0.05134),     # Noon Tuesday
            (13, 0, 1, "Shoulder", 0.09497),     # 1 PM Tuesday (shoulder starts)
            (14, 30, 1, "Shoulder", 0.09497),    # 2:30 PM Tuesday (shoulder)
            (15, 0, 1, "Peak", 0.13861),         # 3 PM Tuesday (peak starts)
            (16, 0, 1, "Peak", 0.13861),         # 4 PM Tuesday (peak)
            (18, 59, 1, "Peak", 0.13861),        # 6:59 PM Tuesday (peak)
            (19, 0, 1, "Off-Peak", 0.05134),     # 7 PM Tuesday (off-peak)
            (16, 0, 5, "Off-Peak", 0.05134),     # 4 PM Saturday (weekend)
            (16, 0, 1, "Off-Peak", 0.05134),     # 4 PM on holiday
        ]
        
        for hour, minute, weekday, expected_period, expected_rate in test_cases:
            mock_now = Mock()
            mock_now.month = 7  # July (summer)
            mock_now.hour = hour
            mock_now.minute = minute
            mock_now.weekday.return_value = weekday
            
            # Last test case is a holiday
            if hour == 16 and weekday == 1 and expected_period == "Off-Peak":
                mock_now.date.return_value = date(2024, 7, 4)  # Independence Day
            else:
                mock_now.date.return_value = date(2024, 7, 2)  # Regular Tuesday
                
            mock_dt_util.now.return_value = mock_now
            
            period = manager.get_current_tou_period()
            rate = manager.get_current_rate()
            
            assert period == expected_period, f"Failed at {hour}:{minute:02d} on weekday {weekday}"
            assert rate == expected_rate, f"Failed rate at {hour}:{minute:02d} on weekday {weekday}"

    def test_pdf_parsing_full_cycle(self, mock_pdf_content, tmp_path):
        """Test complete PDF parsing cycle."""
        from custom_components.xcel_energy_tariff.tariff_manager import XcelTariffManager
        
        mock_hass = Mock()
        cache_path = tmp_path / "cache"
        cache_path.mkdir()
        mock_hass.config.path.return_value = str(cache_path)
        manager = XcelTariffManager(mock_hass, "CO", "electric", "residential_tou")
        
        # Mock the PDF reading
        with patch('builtins.open', mock_open(read_data=b'fake')):
            with patch('PyPDF2.PdfReader') as mock_reader:
                mock_page = Mock()
                mock_page.extract_text.return_value = mock_pdf_content
                mock_reader.return_value.pages = [mock_page]
                
                # Parse the PDF content
                tariff_data = manager._parse_pdf_sync(Path("/fake/path.pdf"))
        
        # Verify all data was extracted
        assert tariff_data["tou_rates"]["summer"]["peak"] == 0.13861
        assert tariff_data["tou_rates"]["summer"]["shoulder"] == 0.09497
        assert tariff_data["tou_rates"]["summer"]["off_peak"] == 0.05134
        assert tariff_data["fixed_charges"]["monthly_service"] == 5.47
        assert "3:00 P.M. - 7:00 P.M." in tariff_data["tou_schedule"]["summer"]["peak_hours"]
        assert "holidays" in tariff_data["tou_schedule"]