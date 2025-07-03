"""Test the Utility Tariff config flow."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.utility_tariff.const import DOMAIN


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.utility_tariff.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.utility_tariff.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Xcel Energy Electric",
                "provider": "xcel_energy",
                "service_type": "electric",
                "rate_schedule": "residential",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Xcel Energy Electric"
    assert result2["data"] == {
        "name": "Xcel Energy Electric",
        "provider": "xcel_energy",
        "service_type": "electric",
        "rate_schedule": "residential",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_provider(hass: HomeAssistant) -> None:
    """Test we handle invalid provider."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test",
            "provider": "invalid_provider",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_provider"


async def test_form_duplicate(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Xcel Energy Electric",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Xcel Energy Electric Duplicate",
            "provider": "xcel_energy",
            "service_type": "electric",
            "rate_schedule": "residential",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


class MockConfigEntry:
    """Mock config entry."""

    def __init__(self, domain, data):
        """Initialize."""
        self.domain = domain
        self.data = data
        self.entry_id = "test_entry_id"

    def add_to_hass(self, hass):
        """Add to hass."""
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][self.entry_id] = self