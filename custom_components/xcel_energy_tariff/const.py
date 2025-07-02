"""Constants for the Xcel Energy Tariff integration."""

DOMAIN = "xcel_energy_tariff"

CONF_STATE = "state"
CONF_SERVICE_TYPE = "service_type"
CONF_RATE_SCHEDULE = "rate_schedule"

SERVICE_TYPE_ELECTRIC = "electric"
SERVICE_TYPE_GAS = "gas"

SERVICE_TYPES = {
    SERVICE_TYPE_ELECTRIC: "Electric",
    SERVICE_TYPE_GAS: "Gas",
}

STATES = {
    "CO": "Colorado",
    "MI": "Michigan", 
    "MN": "Minnesota",
    "NM": "New Mexico",
    "ND": "North Dakota",
    "SD": "South Dakota",
    "TX": "Texas",
    "WI": "Wisconsin",
}

RATE_SCHEDULES = {
    "residential": "Residential",
    "residential_tou": "Residential Time-of-Use",
    "commercial": "Commercial",
    "commercial_tou": "Commercial Time-of-Use",
}

TOU_PERIODS = {
    "peak": "Peak",
    "off_peak": "Off-Peak", 
    "shoulder": "Shoulder",
}

WEEKDAY_PEAK_HOURS = {
    "summer": {"start": 15, "end": 19},  # 3 PM - 7 PM
    "winter": {"start": 16, "end": 20},  # 4 PM - 8 PM
}

# US Federal holidays observed by Xcel Energy
US_HOLIDAYS = [
    "New Year's Day",
    "Memorial Day",
    "Independence Day",
    "Labor Day",
    "Thanksgiving",
    "Christmas Day",
]

XCEL_BASE_URL = "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/"

PDF_URLS = {
    "CO": {
        "electric": f"{XCEL_BASE_URL}PSCo_Electric_Entire_Tariff.pdf",
        "gas": f"{XCEL_BASE_URL}PSCo_Gas_Entire_Tariff.pdf",
        "rate_summary": "https://www.xcelenergy.com/staticfiles/xe/PDF/CO_Residential_Rates_Brochure.pdf",
    },
    "MN": {
        "electric": f"{XCEL_BASE_URL}MN-Rates-&-Regulations-Entire-Electric-Book.pdf",
        "gas": f"{XCEL_BASE_URL}MN-Rates-&-Regulations-Entire-Gas-Book.pdf",
    },
    "WI": {
        "electric": f"{XCEL_BASE_URL}WI-Rates-&-Regulations-Entire-Electric-Book.pdf",
        "gas": f"{XCEL_BASE_URL}WI-Rates-&-Regulations-Entire-Gas-Book.pdf",
    },
    "MI": {
        "electric": f"{XCEL_BASE_URL}MI-Rates-&-Regulations-Entire-Electric-Book.pdf",
        "gas": f"{XCEL_BASE_URL}MI-Rates-&-Regulations-Entire-Gas-Book.pdf",
    },
    "NM": {
        "electric": f"{XCEL_BASE_URL}NM-Rates-&-Regulations-Entire-Electric-Book.pdf",
    },
    "TX": {
        "electric": f"{XCEL_BASE_URL}TX-SPS-Rates-&-Regulations-Entire-Electric-Book.pdf",
    },
    "ND": {
        "electric": f"{XCEL_BASE_URL}ND-Rates-&-Regulations-Entire-Electric-Book.pdf",
    },
    "SD": {
        "electric": f"{XCEL_BASE_URL}SD-Rates-&-Regulations-Entire-Electric-Book.pdf",
    },
}