"""Tests for the Xcel Energy Tariff Manager."""
import pytest
from datetime import datetime, date
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from custom_components.utility_tariff.tariff_manager import GenericTariffManager


class TestTariffManager:
    """Test the GenericTariffManager class."""

    @pytest.fixture
    def mock_hass(self, tmp_path):
        """Mock Home Assistant instance."""
        hass = Mock()
        cache_path = tmp_path / "cache"
        cache_path.mkdir()
        hass.config.path.return_value = str(cache_path)
        hass.async_add_executor_job = Mock(side_effect=lambda func, *args: func(*args))
        return hass

    @pytest.fixture
    def tariff_manager(self, mock_hass):
        """Create a tariff manager instance."""
        return GenericTariffManager(mock_hass, "CO", "electric", "residential_tou")

    def test_holiday_detection(self, tariff_manager):
        """Test holiday detection."""
        # Test fixed holidays
        assert tariff_manager._is_holiday(date(2024, 1, 1)) is True  # New Year's Day
        assert tariff_manager._is_holiday(date(2024, 7, 4)) is True  # Independence Day
        assert tariff_manager._is_holiday(date(2024, 12, 25)) is True  # Christmas
        
        # Test floating holidays
        assert tariff_manager._is_holiday(date(2024, 5, 27)) is True  # Memorial Day 2024
        assert tariff_manager._is_holiday(date(2024, 9, 2)) is True   # Labor Day 2024
        assert tariff_manager._is_holiday(date(2024, 11, 28)) is True # Thanksgiving 2024
        
        # Test non-holidays
        assert tariff_manager._is_holiday(date(2024, 3, 15)) is False  # Random Friday
        assert tariff_manager._is_holiday(date(2024, 6, 10)) is False  # Random Monday
        
        # Test observed holidays
        # July 4, 2026 is a Saturday, so Friday July 3 should be observed
        assert tariff_manager._is_holiday(date(2026, 7, 3)) is True
        # Christmas 2022 was Sunday, so Monday Dec 26 should be observed
        assert tariff_manager._is_holiday(date(2022, 12, 26)) is True

    def test_nth_weekday_of_month(self, tariff_manager):
        """Test nth weekday calculation."""
        # Memorial Day 2024 - Last Monday in May
        memorial_day = tariff_manager._get_nth_weekday_of_month(2024, 5, 0, -1)
        assert memorial_day == date(2024, 5, 27)
        
        # Labor Day 2024 - First Monday in September
        labor_day = tariff_manager._get_nth_weekday_of_month(2024, 9, 0, 1)
        assert labor_day == date(2024, 9, 2)
        
        # Thanksgiving 2024 - Fourth Thursday in November
        thanksgiving = tariff_manager._get_nth_weekday_of_month(2024, 11, 3, 4)
        assert thanksgiving == date(2024, 11, 28)

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_tou_period_weekday_peak(self, mock_dt_util, tariff_manager):
        """Test TOU period detection during weekday peak hours."""
        # Set up tariff data
        tariff_manager._tariff_data = {
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                }
            }
        }
        
        # Tuesday at 4 PM in summer (peak)
        mock_now = Mock()
        mock_now.month = 7  # July
        mock_now.hour = 16  # 4 PM
        mock_now.minute = 0
        mock_now.weekday.return_value = 1  # Tuesday
        mock_now.date.return_value = date(2024, 7, 2)
        mock_dt_util.now.return_value = mock_now
        
        assert tariff_manager.get_current_tou_period() == "Peak"

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_tou_period_weekday_shoulder(self, mock_dt_util, tariff_manager):
        """Test TOU period detection during weekday shoulder hours."""
        tariff_manager._tariff_data = {
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                }
            }
        }
        
        # Wednesday at 2 PM in summer (shoulder)
        mock_now = Mock()
        mock_now.month = 6  # June
        mock_now.hour = 14  # 2 PM
        mock_now.minute = 0
        mock_now.weekday.return_value = 2  # Wednesday
        mock_now.date.return_value = date(2024, 6, 5)
        mock_dt_util.now.return_value = mock_now
        
        assert tariff_manager.get_current_tou_period() == "Shoulder"

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_tou_period_weekday_off_peak(self, mock_dt_util, tariff_manager):
        """Test TOU period detection during weekday off-peak hours."""
        tariff_manager._tariff_data = {
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours",
                }
            }
        }
        
        # Thursday at 10 AM in summer (off-peak)
        mock_now = Mock()
        mock_now.month = 8  # August
        mock_now.hour = 10  # 10 AM
        mock_now.minute = 0
        mock_now.weekday.return_value = 3  # Thursday
        mock_now.date.return_value = date(2024, 8, 1)
        mock_dt_util.now.return_value = mock_now
        
        assert tariff_manager.get_current_tou_period() == "Off-Peak"

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_tou_period_weekend(self, mock_dt_util, tariff_manager):
        """Test TOU period detection during weekend."""
        tariff_manager._tariff_data = {
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours, weekends",
                }
            }
        }
        
        # Saturday at 4 PM (would be peak on weekday, but off-peak on weekend)
        mock_now = Mock()
        mock_now.month = 7  # July
        mock_now.hour = 16  # 4 PM
        mock_now.minute = 0
        mock_now.weekday.return_value = 5  # Saturday
        mock_now.date.return_value = date(2024, 7, 6)
        mock_dt_util.now.return_value = mock_now
        
        assert tariff_manager.get_current_tou_period() == "Off-Peak"

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_tou_period_holiday(self, mock_dt_util, tariff_manager):
        """Test TOU period detection during holiday."""
        tariff_manager._tariff_data = {
            "tou_schedule": {
                "summer": {
                    "peak_hours": "3:00 PM - 7:00 PM",
                    "shoulder_hours": "1:00 PM - 3:00 PM",
                    "off_peak_hours": "All other hours, holidays",
                }
            }
        }
        
        # July 4th at 4 PM (would be peak on regular weekday, but off-peak on holiday)
        mock_now = Mock()
        mock_now.month = 7  # July
        mock_now.hour = 16  # 4 PM
        mock_now.minute = 0
        mock_now.weekday.return_value = 3  # Thursday
        mock_now.date.return_value = date(2024, 7, 4)  # Independence Day
        mock_dt_util.now.return_value = mock_now
        
        assert tariff_manager.get_current_tou_period() == "Off-Peak"

    def test_extract_tou_schedule_from_pdf(self, tariff_manager):
        """Test extracting TOU schedule from PDF text."""
        pdf_text = """
        DEFINITION OF BILLING PERIODS
        The On-Peak, Shoulder and Off-Peak Periods applicable for service hereunder
        shall be as follows:
        On-Peak Period:
        Weekdays except Holidays, between 3:00 p.m. and 7:00 p.m.
        Mountain Time.
        Shoulder Period:
        Weekdays except Holidays, between 1:00 p.m. and 3:00 p.m.
        Mountain Time.
        Off-Peak Period:
        All other hours
        Weekends and Holidays
        """
        
        schedule = tariff_manager._extract_tou_schedule(pdf_text)
        
        # Check that schedule was extracted correctly
        assert "3:00 P.M. - 7:00 P.M." in schedule["summer"]["peak_hours"]
        assert "1:00 P.M. - 3:00 P.M." in schedule["summer"]["shoulder_hours"]
        assert "weekdays except holidays" in schedule["summer"]["applies_to"].lower()
        
        # Winter should have same schedule
        assert schedule["summer"]["peak_hours"] == schedule["winter"]["peak_hours"]

    def test_extract_tou_rates_from_pdf(self, tariff_manager):
        """Test extracting TOU rates from PDF text."""
        pdf_text = """
        Summer Season*
           On-Peak Period                           $0.13861
           Shoulder Period                          $0.09497
           Off-Peak Period                          $0.05134
        Winter Season**
           On-Peak Period                           $0.08727
           Shoulder Period                          $0.06930
           Off-Peak Period                          $0.05134
        """
        
        rates = tariff_manager._extract_tou_rates(pdf_text)
        
        # Check summer rates
        assert rates["summer"]["peak"] == 0.13861
        assert rates["summer"]["shoulder"] == 0.09497
        assert rates["summer"]["off_peak"] == 0.05134
        
        # Check winter rates
        assert rates["winter"]["peak"] == 0.08727
        assert rates["winter"]["shoulder"] == 0.06930
        assert rates["winter"]["off_peak"] == 0.05134

    def test_extract_fixed_charges(self, tariff_manager):
        """Test extracting fixed charges from PDF text."""
        pdf_text = """
        $5.47 Service and Facility Charge
        $1.15 Load Meter Charge
        """
        
        charges = tariff_manager._extract_fixed_charges(pdf_text)
        
        assert charges["monthly_service"] == 5.47

    def test_parse_schedule_times(self, tariff_manager):
        """Test parsing specific time ranges."""
        # Test the time parsing in _determine_period_from_schedule
        schedule = {
            "summer": {
                "peak_hours": "3:00 P.M. - 7:00 P.M.",
                "shoulder_hours": "1:00 P.M. - 3:00 P.M.",
            }
        }
        
        # Mock datetime for 4 PM on a weekday
        mock_now = Mock()
        mock_now.hour = 16
        mock_now.minute = 0
        mock_now.weekday.return_value = 1  # Tuesday
        
        period = tariff_manager._determine_period_from_schedule(
            mock_now, True, schedule, False
        )
        
        assert period == "Peak"
        
        # Test shoulder period (2 PM)
        mock_now.hour = 14
        period = tariff_manager._determine_period_from_schedule(
            mock_now, True, schedule, False
        )
        
        assert period == "Shoulder"
        
        # Test off-peak (10 AM)
        mock_now.hour = 10
        period = tariff_manager._determine_period_from_schedule(
            mock_now, True, schedule, False
        )
        
        assert period == "Off-Peak"

    @patch('custom_components.utility_tariff.tariff_manager.dt_util')
    def test_get_current_rate(self, mock_dt_util, tariff_manager):
        """Test getting current rate based on TOU period."""
        # Set up tariff data with rates
        tariff_manager._tariff_data = {
            "tou_rates": {
                "summer": {
                    "peak": 0.24,
                    "shoulder": 0.12,
                    "off_peak": 0.08,
                },
                "winter": {
                    "peak": 0.20,
                    "shoulder": 0.10,
                    "off_peak": 0.08,
                }
            },
            "tou_schedule": {}
        }
        
        # Test summer peak rate
        mock_now = Mock()
        mock_now.month = 7  # July (summer)
        mock_now.hour = 16  # 4 PM (peak)
        mock_now.minute = 0
        mock_now.day = 2
        mock_now.weekday.return_value = 1  # Tuesday
        mock_now.date.return_value = date(2024, 7, 2)
        mock_now.__sub__ = Mock(return_value=Mock(seconds=0))  # For cache check
        mock_dt_util.now.return_value = mock_now
        
        rate = tariff_manager.get_current_rate()
        assert rate == 0.24  # Summer peak rate
        
        # Test winter off-peak rate
        mock_now.month = 12  # December (winter)
        mock_now.hour = 22  # 10 PM (off-peak)
        rate = tariff_manager.get_current_rate()
        assert rate == 0.08  # Winter off-peak rate