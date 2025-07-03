"""Tests for Utility Tariff sensors."""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.utility_tariff.const import DOMAIN
from custom_components.utility_tariff.sensor import async_setup_entry
from custom_components.utility_tariff.sensors import (
    UtilityCurrentRateSensor,
    UtilityPeakRateSensor,
    UtilityShoulderRateSensor,
    UtilityOffPeakRateSensor,
    UtilityTOUPeriodSensor,
    UtilityFixedChargeSensor,
)


class TestSensors:
    """Test the sensor implementations."""

    @pytest.fixture
    def mock_coordinator(self):
        """Mock data update coordinator."""
        coordinator = Mock(spec=DataUpdateCoordinator)
        
        # Mock hass instance with necessary data
        coordinator.hass = Mock()
        coordinator.hass.data = {
            DOMAIN: {
                "test_entry": {
                    "provider": Mock(name="Test Provider")
                }
            }
        }
        
        coordinator.data = {
            "last_updated": "2024-01-01T12:00:00",
            "current_rate": 0.12,
            "current_period": "Peak",
            "current_season": "summer",
            "is_holiday": False,
            "is_weekend": False,
            "rates": {"standard": 0.11},
            "all_current_rates": {
                "tou_rates": {
                    "peak": 0.24,
                    "shoulder": 0.15,
                    "off_peak": 0.08
                },
                "total_additional": 0.025,
                "fixed_charges": {"monthly_service": 5.47}
            },
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                },
                "winter": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                }
            }
        }
        return coordinator

    @pytest.fixture
    def mock_config_entry(self):
        """Mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "state": "CO",
            "service_type": "electric",
            "rate_schedule": "residential_tou"
        }
        entry.options = {"rate_schedule": "residential_tou"}
        return entry

    def test_current_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test the current rate sensor."""
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        # Check basic attributes
        assert sensor._attr_name == "Current Rate"
        assert sensor._attr_unique_id == "test_entry_current_rate"
        assert sensor._attr_native_unit_of_measurement == "$/kWh"
        
        # Check value
        assert sensor.native_value == 0.12
        
        # Check extra attributes
        attrs = sensor.extra_state_attributes
        assert attrs["period"] == "Peak"
        assert attrs["season"] == "summer"
        assert attrs["is_holiday"] is False
        assert attrs["is_weekend"] is False

    def test_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test peak rate sensor."""
        sensor = UtilityPeakRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Peak Rate"
        assert sensor._attr_unique_id == "test_entry_peak_rate"
        assert sensor.native_value == 0.24

    def test_shoulder_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test shoulder rate sensor."""
        sensor = UtilityShoulderRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Shoulder Rate"
        assert sensor._attr_unique_id == "test_entry_shoulder_rate"
        assert sensor.native_value == 0.15

    def test_off_peak_rate_sensor(self, mock_coordinator, mock_config_entry):
        """Test off-peak rate sensor."""
        sensor = UtilityOffPeakRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Off-Peak Rate"
        assert sensor._attr_unique_id == "test_entry_off_peak_rate"
        assert sensor.native_value == 0.08

    def test_tou_period_sensor(self, mock_coordinator, mock_config_entry):
        """Test TOU period sensor."""
        sensor = UtilityTOUPeriodSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "TOU Period"
        assert sensor._attr_unique_id == "test_entry_tou_period"
        assert sensor.native_value == "Peak"
        
        # Check attributes
        attrs = sensor.extra_state_attributes
        assert attrs["peak_rate"] == 0.24
        assert attrs["shoulder_rate"] == 0.15
        assert attrs["off_peak_rate"] == 0.08
        assert "schedule" in attrs

    def test_fixed_charge_sensor(self, mock_coordinator, mock_config_entry):
        """Test fixed charge sensor."""
        sensor = UtilityFixedChargeSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor._attr_name == "Monthly Service Charge"
        assert sensor._attr_unique_id == "test_entry_fixed_charge"
        assert sensor._attr_native_unit_of_measurement == "$"
        assert sensor.native_value == 5.47

    def test_sensor_with_gas_service(self, mock_coordinator):
        """Test sensors with gas service type."""
        # Set up gas entry in hass data
        mock_coordinator.hass.data[DOMAIN]["gas_entry"] = {
            "provider": Mock(name="Test Provider")
        }
        
        config_entry = Mock()
        config_entry.entry_id = "gas_entry"
        config_entry.data = {
            "state": "CO",
            "service_type": "gas",
            "rate_schedule": "residential"
        }
        config_entry.options = {"rate_schedule": "residential"}
        
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            config_entry
        )
        
        # Gas should use $/therm instead of $/kWh
        assert sensor._attr_native_unit_of_measurement == "$/therm"

    def test_current_rate_sensor_missing_data(self, mock_coordinator, mock_config_entry):
        """Test current rate sensor with missing data."""
        mock_coordinator.data = {}
        
        sensor = UtilityCurrentRateSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        # Should return None when data is missing
        assert sensor.native_value is None

    def test_tou_rates_missing(self, mock_coordinator, mock_config_entry):
        """Test TOU rate sensors when rates are missing."""
        mock_coordinator.data["all_current_rates"] = {}
        
        peak_sensor = UtilityPeakRateSensor(mock_coordinator, mock_config_entry)
        shoulder_sensor = UtilityShoulderRateSensor(mock_coordinator, mock_config_entry)
        off_peak_sensor = UtilityOffPeakRateSensor(mock_coordinator, mock_config_entry)
        
        assert peak_sensor.native_value is None
        assert shoulder_sensor.native_value is None
        assert off_peak_sensor.native_value is None

    def test_fixed_charges_missing(self, mock_coordinator, mock_config_entry):
        """Test fixed charge sensor when charges are missing."""
        mock_coordinator.data["all_current_rates"] = {}
        
        sensor = UtilityFixedChargeSensor(
            mock_coordinator,
            mock_config_entry
        )
        
        assert sensor.native_value is None


@pytest.mark.asyncio
async def test_pdf_download_from_sources_integration(hass: HomeAssistant) -> None:
    """Test that PDF is downloaded from sources.json URL and sensors are created."""
    from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyProvider
    
    # Create a mock config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    config_entry.add_to_hass(hass)
    
    # Mock the PDF content based on actual Google Cloud Storage PDF
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
        
        # Mock PDF parsing with realistic data from the April 2025 PDF
        with patch("PyPDF2.PdfReader") as mock_pdf_reader:
            mock_reader = Mock()
            mock_page = Mock()
            # Use actual text structure from the PDF
            mock_page.extract_text.return_value = """
                Residential ( R)
                Service and Facility per Month 7.10 - 0.81 0.25708 8.17
                Winter Energy per kWh 0.08570 - - 0.00335 0.00940 0.03113 0.00768 - 0.00119 - 0.00450 0.14295
                Summer Energy per kWh 0.10380 - - 0.00335 0.00940 0.03113 0.00768 - 0.00119 (0.00205) 0.00502 0.15952
                Residential Energy Time-Of-Use
                (RE-TOU)
                Service and Facility per Month 7.10 - 0.81 0.25708 8.17
                Winter On-Peak Energy per kWh 0.13171 - - 3.62% 10.16% 33.87% 8.30% - 1.29% - 0.02288
                0.22996
                Winter Shoulder Energy per kWh 0.10460 - - 3.62% 10.16% 33.87% 8.30% - 1.29% - 0.02200 0.18646
                Winter Off-Peak Energy per kWh 0.07749 - - 3.62% 10.16% 33.87% 8.30% - 1.29% - 0.02112 0.14296
                Summer On-Peak Energy per kWh 0.20915 - - 3.62% 10.16% 33.87% 8.30% - 1.29% - 0.02540 0.35424
                Summer Shoulder Energy per kWh 0.14332 - - 3.62% 10.16% 33.87% 8.30% - 1.29% - 0.02326 0.24860
                Summer Off-Peak Energy per kWh 0.07749 - - 3.62% 10.16% 33.87% 8.30% - 1.29% (0.00265) 0.02103 0.14022
            """
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            
            # Create provider and get tariff data
            provider = XcelEnergyProvider()
            result = await provider.get_tariff_data(
                service_type="electric",
                rate_schedule="residential",
                config={},
            )
            
            # Verify the correct URL was used (from sources.json)
            assert mock_session.get.called
            called_url = mock_session.get.call_args[0][0]
            assert "storage.googleapis.com" in called_url
            assert "all-rates-04-01-2025.pdf" in called_url
            
            # Verify data was extracted correctly (using Charge Amount column)
            assert result is not None
            assert "rates" in result
            assert result["rates"]["winter"] == 0.08570
            assert result["rates"]["summer"] == 0.10380
            
            assert "tou_rates" in result
            assert result["tou_rates"]["winter_peak"] == 0.13171
            assert result["tou_rates"]["winter_shoulder"] == 0.10460
            assert result["tou_rates"]["winter_off_peak"] == 0.07749
            assert result["tou_rates"]["summer_peak"] == 0.20915
            assert result["tou_rates"]["summer_shoulder"] == 0.14332
            assert result["tou_rates"]["summer_off_peak"] == 0.07749
            
            assert "fixed_charges" in result
            assert result["fixed_charges"]["service_charge"] == 7.10
            
            assert result["data_source"] == "Xcel Energy PDF"
            assert "pdf_source" in result
            
            # Verify this data can be used for sensor creation
            assert isinstance(result["rates"]["winter"], float)
            assert isinstance(result["rates"]["summer"], float)
            assert all(isinstance(v, float) for v in result["tou_rates"].values())
            assert isinstance(result["fixed_charges"]["service_charge"], float)


class MockConfigEntry:
    """Mock config entry for tests."""

    def __init__(self, domain, data):
        """Initialize."""
        self.domain = domain
        self.data = data
        self.entry_id = "test_entry_id"
        self.unique_id = "test_unique_id"
        self.title = data.get("name", "Test")

    def add_to_hass(self, hass):
        """Add to hass."""
        if "config_entries" not in hass.data:
            hass.data["config_entries"] = {}
        hass.data["config_entries"][self.entry_id] = self