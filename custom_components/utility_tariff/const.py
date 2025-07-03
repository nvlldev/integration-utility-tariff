"""Generic constants for utility tariff integrations."""

# Integration domain - will need to be renamed for full multi-provider support
DOMAIN = "utility_tariff"  # Changed from "xcel_energy_tariff"

# Configuration keys
CONF_PROVIDER = "provider"
CONF_STATE = "state"
CONF_SERVICE_TYPE = "service_type"
CONF_RATE_SCHEDULE = "rate_schedule"

# Generic service types
SERVICE_TYPE_ELECTRIC = "electric"
SERVICE_TYPE_GAS = "gas"
SERVICE_TYPE_WATER = "water"

SERVICE_TYPES = {
    SERVICE_TYPE_ELECTRIC: "Electric",
    SERVICE_TYPE_GAS: "Gas",
    # SERVICE_TYPE_WATER: "Water",  # Coming soon - not added to dict yet
}

# All US states and territories (providers will specify which they support)
ALL_STATES = {
    "AL": "Alabama",
    "AK": "Alaska", 
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "Washington D.C.",
}

# Generic TOU periods (providers can define their own)
TOU_PERIODS = {
    "peak": "Peak",
    "off_peak": "Off-Peak",
    "shoulder": "Shoulder",
    "mid_peak": "Mid-Peak",
    "part_peak": "Part-Peak",
    "super_off_peak": "Super Off-Peak",
}

# Generic rate schedule types (providers define specific schedules)
GENERIC_RATE_TYPES = {
    "residential": "Residential",
    "residential_tou": "Residential Time-of-Use",
    "residential_tiered": "Residential Tiered",
    "residential_ev": "Residential Electric Vehicle",
    "commercial": "Commercial",
    "commercial_tou": "Commercial Time-of-Use",
    "commercial_demand": "Commercial Demand",
    "industrial": "Industrial",
}

# Generic holiday types (providers specify which they observe)
HOLIDAY_TYPES = {
    "us_federal": "US Federal Holidays",
    "california_state": "California State Holidays",
    "texas_state": "Texas State Holidays",
    "new_york_state": "New York State Holidays",
}

# Common US Federal holidays
US_FEDERAL_HOLIDAYS = [
    "New Year's Day",
    "Martin Luther King Jr. Day",
    "Presidents' Day",
    "Memorial Day",
    "Independence Day",
    "Labor Day",
    "Columbus Day",
    "Veterans Day",
    "Thanksgiving",
    "Christmas Day",
]

# Data source types
DATA_SOURCE_PDF = "pdf"
DATA_SOURCE_API = "api"
DATA_SOURCE_FALLBACK = "fallback"
DATA_SOURCE_MANUAL = "manual"

# Rate calculation strategies
RATE_STRATEGY_FLAT = "flat"
RATE_STRATEGY_TIERED = "tiered"
RATE_STRATEGY_TOU = "tou"
RATE_STRATEGY_DEMAND = "demand"
RATE_STRATEGY_REAL_TIME = "real_time"

# Billing period types
BILLING_MONTHLY = "monthly"
BILLING_QUARTERLY = "quarterly"
BILLING_ANNUAL = "annual"

# Season definitions (providers can override)
DEFAULT_SEASONS = {
    "summer": [6, 7, 8, 9],  # June-September
    "winter": [1, 2, 3, 4, 5, 10, 11, 12],  # All other months
}

# Provider capability flags
PROVIDER_CAPABILITIES = {
    "pdf_parsing": "PDF Document Parsing",
    "api_access": "API Access",
    "real_time_rates": "Real-time Rate Updates",
    "demand_charges": "Demand Charge Support",
    "net_metering": "Net Metering Support",
    "green_tariffs": "Green/Renewable Tariffs",
    "ev_rates": "Electric Vehicle Rates",
    "demand_response": "Demand Response Programs",
}

# Error codes for provider operations
ERROR_CODES = {
    "PDF_DOWNLOAD_FAILED": "Failed to download PDF tariff document",
    "PDF_PARSE_FAILED": "Failed to parse PDF content",
    "API_UNAVAILABLE": "Provider API is unavailable",
    "RATE_NOT_FOUND": "Requested rate schedule not found",
    "INVALID_STATE": "Provider does not serve the specified state",
    "INVALID_SERVICE": "Provider does not offer the specified service type",
    "NETWORK_ERROR": "Network connectivity error",
    "AUTHENTICATION_FAILED": "Provider authentication failed",
}

# Update frequencies
UPDATE_FREQUENCIES = {
    "hourly": "Hourly",
    "daily": "Daily", 
    "weekly": "Weekly",
    "monthly": "Monthly",
    "real_time": "Real-time",
}

# Cost sensor types
COST_SENSOR_TYPES = {
    "hourly": "Estimated Hourly Cost",
    "daily": "Estimated Daily Cost", 
    "monthly": "Estimated Monthly Cost",
    "predicted_bill": "Predicted Monthly Bill",
    "net_consumption": "Net Energy Consumption",
    "grid_credit": "Grid Export Credit",
    "solar_export": "Solar Export",
}

# Entity categories for organization
ENTITY_CATEGORIES = {
    "rates": "Current Rates",
    "costs": "Cost Projections",
    "schedule": "TOU Schedule",
    "info": "Tariff Information",
    "net_metering": "Net Metering",
}

# Service names
SERVICE_REFRESH_RATES = "refresh_rates"
SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_CALCULATE_BILL = "calculate_bill"
SERVICE_RESET_METER = "reset_meter"

# Service attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_RESET_ALL = "reset_all"