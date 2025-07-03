# Multi-Provider Utility Tariff Architecture

This document outlines the generified architecture that allows the integration to support multiple utility providers beyond just Xcel Energy.

## Overview

The integration has been refactored from a Xcel Energy-specific implementation into a generic utility rate platform that can support any utility provider through a provider abstraction layer.

## Architecture Components

### 1. Provider Abstraction Layer (`providers/__init__.py`)

The core abstraction defines four main interfaces:

#### `ProviderPDFParser`
- Extracts rates, charges, schedules from provider-specific PDF formats
- Each provider implements their own parsing logic for their document structure

#### `ProviderRateCalculator` 
- Calculates current rates based on time, season, TOU periods
- Handles provider-specific rate calculation strategies (tiered, TOU, demand, etc.)

#### `ProviderURLBuilder`
- Builds URLs for downloading tariff documents
- Provides fallback rates when live data is unavailable

#### `UtilityProvider`
- Main provider class that ties everything together
- Defines service areas, supported rate schedules, and capabilities

### 2. Provider Registry (`providers/registry.py`)

Central registry that:
- Registers all available providers
- Allows querying providers by service area
- Handles provider discovery for config flow

### 3. Generic Tariff Manager (`generic_tariff_manager.py`)

Provider-agnostic manager that:
- Delegates all operations to provider-specific implementations
- Handles caching, error recovery, and repair issues
- Maintains compatibility with existing coordinator architecture

### 4. Provider Implementations

#### Xcel Energy (`providers/xcel_energy.py`)
Complete implementation for Xcel Energy including:
- PDF parsing for Xcel's specific document format
- TOU schedules and holiday definitions
- Rate calculation for tiered and TOU structures
- Fallback rates for all 8 served states

#### Template (`providers/provider_template.py`)
Example implementation showing how to add Pacific Gas & Electric (PG&E):
- Different PDF parsing patterns
- California-specific holidays and seasons
- PG&E rate schedule naming (E-1, E-6, etc.)
- Baseline/tier rate structures

## Adding New Providers

To add a new utility provider:

### 1. Create Provider Implementation

```python
class NewUtilityProvider(UtilityProvider):
    def __init__(self):
        super().__init__("new_utility_id")
    
    @property
    def name(self) -> str:
        return "New Utility Company"
    
    @property
    def supported_states(self) -> Dict[str, List[str]]:
        return {
            "electric": ["STATE1", "STATE2"],
            "gas": ["STATE1"]
        }
    
    # Implement all required methods...
```

### 2. Implement PDF Parser

```python
class NewUtilityPDFParser(ProviderPDFParser):
    def extract_rates(self, text: str) -> Dict[str, Any]:
        # Provider-specific regex patterns
        rate_pattern = r"Your rate pattern here"
        # ... parsing logic
        
    # Implement all required parsing methods...
```

### 3. Implement Rate Calculator

```python
class NewUtilityRateCalculator(ProviderRateCalculator):
    def calculate_current_rate(self, time: datetime, tariff_data: Dict[str, Any]) -> Optional[float]:
        # Provider-specific rate calculation
        # Handle tiered rates, TOU, demand charges, etc.
        
    # Implement all required calculation methods...
```

### 4. Register Provider

```python
# In providers/registry.py
from .new_utility import NewUtilityProvider

def initialize_providers():
    # Existing providers...
    
    # Add new provider
    new_provider = NewUtilityProvider()
    ProviderRegistry.register_provider(new_provider)
```

## Provider Capabilities

The system supports various provider capabilities:

### Rate Structures
- **Flat Rate**: Single rate regardless of time/usage
- **Tiered**: Different rates based on usage levels
- **Time-of-Use (TOU)**: Rates vary by time of day/season
- **Demand**: Additional charges based on peak demand
- **Real-time**: Dynamic pricing based on market conditions

### Data Sources
- **PDF Parsing**: Extract from utility tariff documents
- **API Access**: Direct integration with utility APIs
- **Fallback Rates**: Static rates when live data unavailable
- **Manual Entry**: User-provided rates

### Features
- **Net Metering**: Solar export credit calculations
- **Demand Charges**: Peak demand billing
- **Green Tariffs**: Renewable energy programs
- **EV Rates**: Electric vehicle time-of-use rates
- **Demand Response**: Dynamic rate programs

## Configuration Flow Changes

The config flow now includes provider selection:

1. **Provider Selection**: Choose from available providers
2. **State/Service Filtering**: Only show relevant options
3. **Rate Schedule**: Provider-specific rate plans
4. **Advanced Options**: Provider-specific configurations

```yaml
# Example configuration
provider: "pge"
state: "CA"
service_type: "electric"
rate_schedule: "E-6"  # PG&E residential TOU
consumption_entity: "sensor.home_energy"
return_entity: "sensor.solar_export"
```

## Migration Strategy

The architecture includes backward compatibility:

### Existing Installations
- Automatically migrated to multi-provider format
- Existing Xcel Energy configs get `provider: "xcel_energy"` added
- No breaking changes to entity names or functionality

### Entity Naming
- Maintains provider-specific prefixes: "Xcel Colorado Current Rate"
- New providers use their own branding: "PG&E California Current Rate"

### Domain Transition
- Current domain: `xcel_energy_tariff`
- Future domain: `utility_tariff` (for new installations)
- Existing installations continue using current domain

## Testing Multi-Provider Support

### Unit Tests
Each provider should have comprehensive tests:

```python
def test_pge_rate_calculation():
    provider = PGEProvider()
    calculator = provider.rate_calculator
    
    # Test baseline rate calculation
    result = calculator.calculate_current_rate(datetime.now(), test_data)
    assert result == expected_rate

def test_pge_pdf_parsing():
    parser = PGEProvider().pdf_parser
    rates = parser.extract_rates(sample_pge_pdf_text)
    
    assert rates["baseline"] == 0.25
    assert rates["tier_2"] == 0.32
```

### Integration Tests
Test provider discovery and configuration:

```python
def test_provider_discovery():
    initialize_providers()
    providers = get_providers_for_state("CA", "electric")
    
    provider_names = [p.name for p in providers]
    assert "Pacific Gas & Electric" in provider_names
    assert "Xcel Energy" not in provider_names  # Doesn't serve CA
```

## Future Enhancements

### Additional Providers
The architecture makes it easy to add:
- **ConEd** (New York)
- **Duke Energy** (Multi-state)
- **Southern Company** (Southeast)
- **ComEd** (Illinois)
- **PSEG** (New Jersey/Long Island)

### Enhanced Features
- **API Integrations**: Direct utility API connections
- **Real-time Rates**: Live pricing updates
- **Demand Response**: Automated rate adjustments
- **Carbon Tracking**: Emissions-based rate premiums
- **Community Solar**: Shared renewable programs

### User Experience
- **Provider Auto-Detection**: Suggest providers based on location
- **Rate Comparison**: Compare plans within same provider
- **Bill Validation**: Compare predictions with actual bills
- **Usage Optimization**: Recommend rate plan changes

## Benefits of Multi-Provider Architecture

### For Users
- Single integration supporting multiple utilities
- Consistent interface across all providers
- Easy migration when moving between service territories

### For Developers
- Pluggable architecture for adding new providers
- Shared infrastructure for common functionality
- Provider-specific customization where needed

### For the Community
- Collaborative development of provider implementations
- Shared testing and validation framework
- Faster expansion to new service territories

This architecture transforms the integration from a single-utility solution into a comprehensive utility rate platform that can serve Home Assistant users across North America and beyond.