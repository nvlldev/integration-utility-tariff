"""Common fixtures for Utility Tariff tests."""
import pytest
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant


@pytest.fixture
def hass() -> HomeAssistant:
    """Return a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.async_block_till_done = Mock()
    hass.config_entries = Mock()
    hass.config_entries.flow = Mock()
    hass.config_entries.async_forward_entry_setups = Mock()
    return hass


@pytest.fixture
def mock_pdf_content():
    """Return mock PDF content for testing."""
    return """
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
    
    ENERGY CHARGE:
    All kilowatt hours used per kWh
    Summer Season*
       On-Peak Period                           $0.13861
       Shoulder Period                          $0.09497
       Off-Peak Period                          $0.05134
    Winter Season**
       On-Peak Period                           $0.08727
       Shoulder Period                          $0.06930
       Off-Peak Period                          $0.05134
       
    $5.47 Service and Facility Charge
    
    Holidays include: New Year's Day, Memorial Day, Independence Day,
    Labor Day, Thanksgiving Day, and Christmas Day.
    """