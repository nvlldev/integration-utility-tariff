"""Template for adding new utility providers.

This template demonstrates how to implement providers with different data sources:
- PDF-based extraction (like Xcel Energy)
- REST API integration
- HTML web scraping
- Real-time pricing APIs
- CSV/Excel file downloads
"""

import re
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
import json
from bs4 import BeautifulSoup  # For HTML scraping example
import csv
from io import StringIO
import PyPDF2  # For PDF example
from io import BytesIO  # For PDF example

from . import (
    UtilityProvider,
    ProviderDataExtractor,
    ProviderRateCalculator,
    ProviderDataSource,
)

_LOGGER = logging.getLogger(__name__)


# Example 1: API-based data extractor
class ExampleAPIExtractor(ProviderDataExtractor):
    """Example REST API-based data extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch tariff data from REST API."""
        api_endpoint = kwargs.get("api_endpoint")
        api_key = kwargs.get("api_key")
        state = kwargs.get("state")
        rate_schedule = kwargs.get("rate_schedule")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        
        params = {
            "state": state,
            "rate_type": rate_schedule,
            "effective_date": datetime.now().isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_endpoint, headers=headers, params=params) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                data = await response.json()
        
        # Transform API response to standard format
        return {
            "rates": {
                "summer": data.get("summer_rate"),
                "winter": data.get("winter_rate"),
            },
            "tou_rates": data.get("time_of_use_rates", {}),
            "fixed_charges": {
                "monthly_service": data.get("service_charge"),
            },
            "tou_schedule": data.get("tou_schedule"),
            "season_definitions": data.get("seasons"),
            "effective_date": data.get("effective_date"),
            "data_source": "api",
            "api_endpoint": api_endpoint,
        }
    
    def get_data_source_type(self) -> str:
        return "api"
    
    def requires_file_download(self) -> bool:
        return False
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not data.get("rates"):
            return False, "No rates found in API response"
        return True, None


# Example 2: HTML scraping data extractor
class ExampleHTMLExtractor(ProviderDataExtractor):
    """Example HTML web scraping data extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch and scrape tariff data from HTML pages."""
        url = kwargs.get("url")
        state = kwargs.get("state")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch webpage: {response.status}")
                html_content = await response.text()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Example: Find rate table
        rate_table = soup.find('table', {'class': 'rate-schedule'})
        rates = {}
        
        if rate_table:
            for row in rate_table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    period = cells[0].text.strip().lower()
                    rate = float(cells[1].text.strip().replace('$', '').replace('/kWh', ''))
                    rates[period] = rate
        
        # Example: Find TOU information
        tou_section = soup.find('div', {'id': 'time-of-use'})
        tou_rates = {}
        if tou_section:
            # Parse TOU rates from HTML structure
            pass
        
        return {
            "rates": rates,
            "tou_rates": tou_rates,
            "fixed_charges": self._extract_fixed_charges_from_html(soup),
            "effective_date": self._extract_date_from_html(soup),
            "data_source": "html",
            "source_url": url,
        }
    
    def get_data_source_type(self) -> str:
        return "html"
    
    def requires_file_download(self) -> bool:
        return False
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not data.get("rates"):
            return False, "No rates found on webpage"
        return True, None
    
    def _extract_fixed_charges_from_html(self, soup) -> Dict[str, float]:
        """Extract fixed charges from HTML."""
        charges = {}
        charge_div = soup.find('div', {'class': 'monthly-charges'})
        if charge_div:
            # Extract charges based on HTML structure
            pass
        return charges
    
    def _extract_date_from_html(self, soup) -> Optional[str]:
        """Extract effective date from HTML."""
        date_elem = soup.find('span', {'class': 'effective-date'})
        if date_elem:
            return date_elem.text.strip()
        return None


# Example 3: Real-time pricing API extractor
class ExampleRealTimeExtractor(ProviderDataExtractor):
    """Example real-time pricing data extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch real-time pricing data."""
        api_endpoint = kwargs.get("realtime_endpoint")
        location_id = kwargs.get("location_id")
        
        # Get current and forecasted prices
        async with aiohttp.ClientSession() as session:
            # Current price
            async with session.get(f"{api_endpoint}/current/{location_id}") as response:
                current_data = await response.json()
            
            # Price forecast (next 24 hours)
            async with session.get(f"{api_endpoint}/forecast/{location_id}") as response:
                forecast_data = await response.json()
        
        # Build rate structure from real-time data
        current_price = current_data.get("price_per_kwh")
        
        # Calculate dynamic TOU-like periods based on price levels
        price_levels = self._categorize_prices(forecast_data.get("hourly_prices", []))
        
        return {
            "rates": {
                "realtime": current_price,
                "average_today": price_levels.get("average"),
            },
            "tou_rates": {
                "dynamic": {
                    "high": price_levels.get("high"),
                    "medium": price_levels.get("medium"),
                    "low": price_levels.get("low"),
                }
            },
            "price_forecast": forecast_data.get("hourly_prices", []),
            "data_source": "realtime_api",
            "last_update": datetime.now().isoformat(),
            "update_frequency": "5_minutes",
        }
    
    def get_data_source_type(self) -> str:
        return "realtime_api"
    
    def requires_file_download(self) -> bool:
        return False
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not data.get("rates", {}).get("realtime"):
            return False, "No real-time price available"
        return True, None
    
    def _categorize_prices(self, hourly_prices: List[Dict]) -> Dict[str, float]:
        """Categorize prices into high/medium/low bands."""
        if not hourly_prices:
            return {}
        
        prices = [p["price"] for p in hourly_prices]
        sorted_prices = sorted(prices)
        
        # Simple tercile approach
        low_threshold = sorted_prices[len(sorted_prices) // 3]
        high_threshold = sorted_prices[2 * len(sorted_prices) // 3]
        
        return {
            "high": high_threshold,
            "medium": (low_threshold + high_threshold) / 2,
            "low": low_threshold,
            "average": sum(prices) / len(prices),
        }


# Example 4: CSV download extractor
class ExampleCSVExtractor(ProviderDataExtractor):
    """Example CSV file download and parsing extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch and parse tariff data from CSV file."""
        csv_url = kwargs.get("csv_url")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(csv_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download CSV: {response.status}")
                csv_content = await response.text()
        
        # Parse CSV
        csv_reader = csv.DictReader(StringIO(csv_content))
        rates_by_schedule = {}
        
        for row in csv_reader:
            schedule = row.get("rate_schedule")
            if schedule == kwargs.get("rate_schedule"):
                rates_by_schedule = {
                    "summer": float(row.get("summer_rate", 0)),
                    "winter": float(row.get("winter_rate", 0)),
                }
                break
        
        return {
            "rates": rates_by_schedule,
            "fixed_charges": {
                "monthly_service": 15.0  # Would come from CSV
            },
            "data_source": "csv",
            "csv_url": csv_url,
            "last_update": datetime.now().isoformat(),
        }
    
    def get_data_source_type(self) -> str:
        return "csv"
    
    def requires_file_download(self) -> bool:
        return True
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not data.get("rates"):
            return False, "No rates found in CSV"
        return True, None


# Example 5: PDF-based extractor (similar to Xcel)
class ExamplePDFExtractor(ProviderDataExtractor):
    """Example PDF-based data extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch and extract tariff data from PDF."""
        url = kwargs.get("url")
        if not url:
            raise ValueError("No PDF URL provided")
        
        # Download PDF
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download PDF: {response.status}")
                pdf_content = await response.read()
        
        # Extract text from PDF
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Extract text from relevant pages
        text = ""
        for page in pdf_reader.pages[:10]:  # First 10 pages
            text += page.extract_text()
        
        # Extract data using regex patterns
        return {
            "rates": self._extract_rates(text),
            "tou_rates": self._extract_tou_rates(text),
            "fixed_charges": self._extract_fixed_charges(text),
            "effective_date": self._extract_effective_date(text),
            "data_source": "pdf",
            "pdf_url": url,
        }
    
    def get_data_source_type(self) -> str:
        return "pdf"
    
    def requires_file_download(self) -> bool:
        return True
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not data.get("rates"):
            return False, "No rates found in PDF"
        return True, None
    
    def _extract_rates(self, text: str) -> Dict[str, float]:
        """Extract rates from PDF text."""
        # Implementation specific to provider's PDF format
        return {}
    
    def _extract_tou_rates(self, text: str) -> Dict[str, Any]:
        """Extract TOU rates from PDF text."""
        # Implementation specific to provider's PDF format
        return {}
    
    def _extract_fixed_charges(self, text: str) -> Dict[str, float]:
        """Extract fixed charges from PDF text."""
        # Implementation specific to provider's PDF format
        return {}
    
    def _extract_effective_date(self, text: str) -> Optional[str]:
        """Extract effective date from PDF text."""
        # Implementation specific to provider's PDF format
        return None


class ExampleRateCalculator(ProviderRateCalculator):
    """Example rate calculator that handles different data source types."""
    
    def calculate_current_rate(self, time: datetime, tariff_data: Dict[str, Any]) -> Optional[float]:
        """Calculate current rate based on data source type."""
        data_source = tariff_data.get("data_source")
        
        if data_source == "realtime_api":
            # For real-time pricing, just return the current rate
            return tariff_data.get("rates", {}).get("realtime")
        
        elif data_source == "api" or data_source == "html" or data_source == "csv":
            # For traditional sources, use TOU or seasonal logic
            rates = tariff_data.get("rates", {})
            tou_rates = tariff_data.get("tou_rates", {})
            
            if tou_rates:
                period = self.get_tou_period(time, tariff_data)
                season = "summer" if self.is_summer_season(time, tariff_data) else "winter"
                season_rates = tou_rates.get(season, {})
                return season_rates.get(period.lower().replace("-", "_"))
            else:
                # Simple seasonal rates
                season = "summer" if self.is_summer_season(time, tariff_data) else "winter"
                return rates.get(season)
        
        return None
    
    def get_tou_period(self, time: datetime, tariff_data: Dict[str, Any]) -> str:
        """Get current TOU period."""
        # Implementation specific to provider
        hour = time.hour
        
        if 15 <= hour < 19:  # 3 PM - 7 PM
            return "Peak"
        elif 13 <= hour < 15:  # 1 PM - 3 PM
            return "Shoulder"
        else:
            return "Off-Peak"
    
    def is_summer_season(self, time: datetime, season_config: Dict[str, Any]) -> bool:
        """Determine if time is in summer season."""
        summer_months = season_config.get("summer_months", "6,7,8,9")
        if isinstance(summer_months, str):
            months = [int(m.strip()) for m in summer_months.split(",")]
        else:
            months = summer_months
        
        return time.month in months
    
    def is_holiday(self, date: date, holiday_config: Dict[str, Any]) -> bool:
        """Check if date is a holiday."""
        # Simplified holiday check
        federal_holidays = {
            (1, 1): "New Year's Day",
            (7, 4): "Independence Day",
            (12, 25): "Christmas Day"
        }
        
        return (date.month, date.day) in federal_holidays
    
    def get_all_current_rates(self, time: datetime, tariff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all current rates and charges."""
        result = {}
        
        # Get base rates
        rates = tariff_data.get("rates", {})
        result.update(rates)
        
        # Get TOU rates if available
        tou_rates = tariff_data.get("tou_rates", {})
        if tou_rates:
            result["tou_rates"] = tou_rates
        
        # Get fixed charges
        fixed_charges = tariff_data.get("fixed_charges", {})
        result["fixed_charges"] = fixed_charges
        
        return result


class ExampleDataSource(ProviderDataSource):
    """Example data source configuration supporting multiple source types."""
    
    # This provider supports different data sources by state
    STATE_DATA_SOURCES = {
        "CA": "api",      # California has API access
        "NY": "html",     # New York requires web scraping
        "TX": "realtime", # Texas has real-time pricing
        "FL": "csv",      # Florida provides CSV downloads
        # Other states might use PDF
    }
    
    API_ENDPOINTS = {
        "CA": "https://api.example-utility.com/v2/rates",
        "TX": "https://realtime.example-ercot.com/api/prices",
    }
    
    WEB_URLS = {
        "NY": "https://www.example-utility.com/rates/residential",
        "FL": "https://www.example-utility.com/download/rates.csv",
    }
    
    def get_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        """Get configuration based on state's data source type."""
        source_type = self.STATE_DATA_SOURCES.get(state, "pdf")
        
        if source_type == "api":
            return {
                "type": "api",
                "api_endpoint": self.API_ENDPOINTS.get(state),
                "api_key": "your-api-key",  # Would come from config
            }
        elif source_type == "realtime":
            return {
                "type": "realtime_api",
                "realtime_endpoint": self.API_ENDPOINTS.get(state),
                "location_id": f"{state}_ZONE_1",  # Would be configured
            }
        elif source_type == "html":
            return {
                "type": "html",
                "url": self.WEB_URLS.get(state),
            }
        elif source_type == "csv":
            return {
                "type": "csv",
                "csv_url": self.WEB_URLS.get(state),
            }
        else:
            # Default to PDF
            return {
                "type": "pdf",
                "url": f"https://example.com/tariffs/{state}_{service_type}.pdf",
            }
    
    def get_fallback_rates(self, state: str, service_type: str) -> Dict[str, Any]:
        """Get fallback rates for given state and service type."""
        # Provider-specific fallback rates
        fallback_rates = {
            "CA": {
                "electric": {
                    "rates": {"summer": 0.25, "winter": 0.20},
                    "fixed_charges": {"monthly_service": 10.00}
                }
            },
            # Add other states...
        }
        
        return fallback_rates.get(state, {}).get(service_type, {})
    
    def supports_real_time_rates(self) -> bool:
        """Check if any state supports real-time rates."""
        return "realtime" in self.STATE_DATA_SOURCES.values()
    
    def get_update_interval(self) -> timedelta:
        """Get update interval based on fastest data source."""
        if "realtime" in self.STATE_DATA_SOURCES.values():
            return timedelta(minutes=5)  # Real-time needs frequent updates
        elif "api" in self.STATE_DATA_SOURCES.values():
            return timedelta(hours=1)    # API data might update hourly
        else:
            return timedelta(days=1)     # Static data updates daily


class ExampleProvider(UtilityProvider):
    """Example utility provider implementation supporting multiple data sources."""
    
    def __init__(self):
        super().__init__("example_provider")
        self._data_extractors = {
            "api": ExampleAPIExtractor(),
            "html": ExampleHTMLExtractor(),
            "realtime_api": ExampleRealTimeExtractor(),
            "csv": ExampleCSVExtractor(),
            "pdf": ExamplePDFExtractor(),
        }
    
    @property
    def name(self) -> str:
        return "Example Energy Company"
    
    @property
    def short_name(self) -> str:
        return "Example"
    
    @property
    def supported_states(self) -> Dict[str, List[str]]:
        return {
            "electric": ["CA", "NY", "TX", "FL", "AZ", "NV"],
            "gas": ["CA", "NY", "FL"]
        }
    
    @property
    def supported_rate_schedules(self) -> Dict[str, List[str]]:
        return {
            "electric": [
                "residential",
                "residential_tou",
                "residential_ev",
                "commercial",
                "commercial_tou"
            ],
            "gas": [
                "residential_gas",
                "commercial_gas"
            ]
        }
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "pdf_parsing",
            "api_integration",
            "html_scraping",
            "realtime_pricing",
            "csv_import",
            "tou_rates",
            "seasonal_rates",
            "tiered_rates",
            "net_metering"
        ]
    
    def _load_provider_config(self) -> Dict[str, Any]:
        return {
            "holidays": "us_federal",
            "season_months": {
                "summer": [6, 7, 8, 9],
                "winter": [1, 2, 3, 4, 5, 10, 11, 12]
            },
            "tou_schedule": {
                "peak": {"start": 15, "end": 19},
                "shoulder": {"start": 13, "end": 15}
            }
        }
    
    def _create_data_extractor(self) -> ProviderDataExtractor:
        # This would be called during init, but we'll return a default
        # The actual extractor is selected dynamically based on state
        return ExampleAPIExtractor()  # Default extractor
    
    def get_data_extractor_for_state(self, state: str) -> ProviderDataExtractor:
        """Get the appropriate data extractor based on state."""
        source_type = ExampleDataSource.STATE_DATA_SOURCES.get(state, "pdf")
        return self._data_extractors.get(source_type, ExamplePDFExtractor())
    
    def _create_rate_calculator(self) -> ProviderRateCalculator:
        return ExampleRateCalculator()
    
    def _create_data_source(self) -> ProviderDataSource:
        return ExampleDataSource()


# To add this provider to the registry, you would add this to registry.py:
#
# from .provider_template import ExampleProvider
# 
# def initialize_providers():
#     # Register existing providers...
#     
#     # Register Example provider
#     example_provider = ExampleProvider()
#     ProviderRegistry.register_provider(example_provider)