# Changelog

All notable changes to the Utility Tariff integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-XX

### Added
- **Multi-Provider Support**: Complete rewrite to support multiple utility providers beyond Xcel Energy
- **Provider Abstraction Layer**: Flexible architecture for adding new utility providers
- **Multiple Data Sources**: Support for PDF, API, HTML scraping, CSV, and real-time pricing data sources
- **Return Entity Support**: Track energy returned to grid for solar/net metering calculations
- **Net Consumption Sensors**: Calculate net energy usage (consumption - solar export)
- **Grid Credit Sensors**: Track credits earned from excess solar generation
- **Provider Registry**: Dynamic provider registration and discovery system
- **Data Source Agnostic**: Providers can use different data sources for different states/regions
- **Enhanced Cost Projections**: Improved bill prediction with net metering support
- **Provider Templates**: Comprehensive template and documentation for adding new providers

### Changed
- **Domain Name**: Changed from `xcel_energy_tariff` to `utility_tariff`
- **Integration Name**: Changed from "Xcel Energy Tariff" to "Utility Tariff"
- **Entity Naming**: All entities now use provider short name (e.g., "Xcel Colorado" instead of "Xcel Energy Colorado")
- **Configuration Flow**: Added provider selection as first step
- **State Filtering**: States shown based on selected provider's coverage area
- **Rate Schedule Options**: Dynamic based on provider capabilities
- **Update Intervals**: Can vary by provider and data source type

### Fixed
- **Return Entity Calculations**: Fixed null handling in return energy calculations
- **Coordinator Updates**: Improved error handling and fallback mechanisms
- **Season Detection**: More flexible season definition support per provider

### Migration Notes
- Existing Xcel Energy configurations will automatically migrate to the new format
- Provider field will be set to "xcel_energy" for existing installations
- No manual intervention required - existing sensors will continue working
- Entity IDs remain unchanged to preserve history and automations

### Breaking Changes
- Custom components using the old `XcelTariffManager` class need to update to `ProviderTariffManager`
- Direct PDF URL configuration is replaced by provider-based configuration

### Supported Providers
- **Xcel Energy**: Full support for all existing Xcel Energy states (CO, MN, WI, MI, NM, ND, SD, TX)
- Additional providers can be added by implementing the provider interface

### Technical Details
- Requires Home Assistant 2023.12.0 or newer
- Python 3.11 or newer
- New dependencies: beautifulsoup4 (for HTML scraping providers)

## [Previous Versions]

### [0.3.0] - 2023-12-XX
- Added return entity support for solar installations
- Improved PDF extraction accuracy
- Added predicted bill sensor

### [0.2.0] - 2023-11-XX
- Enhanced Time-of-Use rate support
- Added seasonal rate detection
- Improved configuration flow

### [0.1.0] - 2023-10-XX
- Initial release
- Support for Xcel Energy PDF tariff extraction
- Basic rate sensors
- Colorado state support