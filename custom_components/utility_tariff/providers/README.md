# Adding New Utility Providers

This guide explains how to add support for new utility providers to the Utility Tariff integration.

## Overview

The integration supports multiple data source types:
- **PDF**: Extract rates from PDF documents (like Xcel Energy)
- **API**: Fetch rates from REST APIs  
- **HTML**: Scrape rates from web pages
- **Real-time**: Dynamic pricing APIs (like ERCOT in Texas)
- **CSV**: Download and parse CSV files

## Quick Start

1. Copy `provider_template.py` to create your new provider
2. Implement the required abstract methods
3. Register your provider in `registry.py`

## Provider Architecture

Each provider consists of four main components:

### 1. Data Extractor
Fetches and extracts tariff data from the provider's data source.

```python
class MyProviderAPIExtractor(ProviderDataExtractor):
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        # Fetch data from API, PDF, HTML, etc.
        # Return standardized tariff data structure
        
    def get_data_source_type(self) -> str:
        return "api"  # or "pdf", "html", "realtime_api", "csv"
```

### 2. Rate Calculator
Calculates current rates based on time, season, and TOU periods.

```python
class MyProviderRateCalculator(ProviderRateCalculator):
    def calculate_current_rate(self, time: datetime, tariff_data: Dict[str, Any]) -> Optional[float]:
        # Calculate rate based on provider's tariff structure
```

### 3. Data Source Configuration
Provides URLs, API endpoints, and configuration for accessing data.

```python
class MyProviderDataSource(ProviderDataSource):
    def get_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        # Return configuration based on state/service
        return {
            "type": "api",
            "api_endpoint": "https://api.myprovider.com/rates",
            "api_key": "your-key"
        }
```

### 4. Provider Implementation
Ties everything together and defines supported states/schedules.

```python
class MyProvider(UtilityProvider):
    @property
    def supported_states(self) -> Dict[str, List[str]]:
        return {
            "electric": ["CA", "NV", "AZ"],
            "gas": ["CA", "NV"]
        }
```

## Example: Multi-Source Provider

A provider can support different data sources for different states:

```python
class MultiSourceProvider(UtilityProvider):
    def __init__(self):
        super().__init__("multi_source")
        self._data_extractors = {
            "api": APIExtractor(),
            "html": HTMLExtractor(),
            "pdf": PDFExtractor(),
        }
    
    def get_data_extractor_for_state(self, state: str) -> ProviderDataExtractor:
        # California uses API
        if state == "CA":
            return self._data_extractors["api"]
        # Texas uses HTML scraping
        elif state == "TX":
            return self._data_extractors["html"]
        # Others use PDF
        else:
            return self._data_extractors["pdf"]
```

## Data Structure

All extractors must return data in this standardized format:

```python
{
    "rates": {
        "summer": 0.12,      # $/kWh
        "winter": 0.10,      # $/kWh
        "tier_1": 0.11,      # Optional tiered rates
        "tier_2": 0.15,
    },
    "tou_rates": {           # Optional TOU rates
        "summer": {
            "peak": 0.25,
            "shoulder": 0.15,
            "off_peak": 0.10
        },
        "winter": {
            "peak": 0.20,
            "shoulder": 0.12,
            "off_peak": 0.08
        }
    },
    "fixed_charges": {
        "monthly_service": 15.00,  # Monthly service charge
        "demand_charge": 10.00,    # Optional demand charge
    },
    "tou_schedule": {        # Optional TOU schedule
        "peak_hours": "3 PM - 7 PM",
        "shoulder_hours": "1 PM - 3 PM",
    },
    "season_definitions": {
        "summer_months": "6,7,8,9",
    },
    "effective_date": "January 1, 2024",
    "data_source": "api",    # Source type used
}
```

## Real-World Examples

### PG&E (Pacific Gas & Electric)
- **Data Source**: HTML scraping from rate schedule pages
- **Features**: Tiered rates, TOU options, baseline allowances
- **States**: California

### ConEd (Consolidated Edison)
- **Data Source**: API integration
- **Features**: Real-time pricing, demand charges
- **States**: New York

### ERCOT (Texas)
- **Data Source**: Real-time pricing API
- **Features**: 5-minute pricing updates, day-ahead forecasts
- **States**: Texas

## Testing Your Provider

1. Test data extraction:
```python
extractor = MyProviderExtractor()
data = await extractor.fetch_tariff_data(state="CA", service_type="electric")
assert data["rates"]["summer"] > 0
```

2. Test rate calculations:
```python
calculator = MyProviderRateCalculator()
summer_noon = datetime(2024, 7, 15, 12, 0)
rate = calculator.calculate_current_rate(summer_noon, data)
assert rate == expected_rate
```

3. Test with Home Assistant:
- Add provider to registry
- Configure through UI
- Verify sensors update correctly

## Best Practices

1. **Error Handling**: Always provide fallback rates
2. **Caching**: Cache API/web responses appropriately
3. **Validation**: Validate all extracted data
4. **Documentation**: Document rate structures and special cases
5. **Updates**: Set appropriate update intervals based on data source

## Adding to Registry

Once your provider is complete, register it in `registry.py`:

```python
from .my_provider import MyProvider

def initialize_providers():
    # Register existing providers...
    
    # Register your provider
    my_provider = MyProvider()
    ProviderRegistry.register_provider(my_provider)
```