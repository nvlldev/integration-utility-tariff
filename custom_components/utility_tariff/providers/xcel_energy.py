"""Xcel Energy provider implementation."""

import re
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
import PyPDF2
from io import BytesIO

from . import (
    UtilityProvider,
    ProviderDataExtractor,
    ProviderRateCalculator,
    ProviderDataSource,
)

_LOGGER = logging.getLogger(__name__)


class XcelEnergyPDFExtractor(ProviderDataExtractor):
    """Xcel Energy PDF-based data extractor."""
    
    async def fetch_tariff_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch and extract tariff data from Xcel Energy PDF with retry mechanism."""
        url = kwargs.get("url")
        if not url:
            raise ValueError("No PDF URL provided")
        
        # Retry configuration
        max_retries = 3
        retry_delay = 2
        pdf_content = None
        last_error = None
        
        # Retry PDF download
        for attempt in range(max_retries):
            try:
                _LOGGER.debug("Downloading PDF from %s (attempt %d/%d)", url, attempt + 1, max_retries)
                
                # Download PDF with timeout
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}: {response.reason}")
                        pdf_content = await response.read()
                        _LOGGER.debug("Successfully downloaded PDF (%d bytes)", len(pdf_content))
                        break
                        
            except Exception as e:
                last_error = e
                _LOGGER.warning("PDF download attempt %d failed: %s", attempt + 1, str(e))
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        if pdf_content is None:
            raise Exception(f"Failed to download PDF after {max_retries} attempts: {last_error}")
        
        # Retry PDF parsing
        combined_text = None
        for attempt in range(2):  # Less retries for parsing
            try:
                _LOGGER.debug("Parsing PDF (attempt %d)", attempt + 1)
                
                # Extract text from PDF
                pdf_file = BytesIO(pdf_content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                # Score pages and extract from most relevant ones
                rate_schedule = kwargs.get("rate_schedule", "")
                scored_pages = []
                
                for i, page in enumerate(pdf_reader.pages):
                    try:
                        text = page.extract_text()
                        score = self._score_pdf_page(text, rate_schedule)
                        if score > 0:
                            scored_pages.append((i, score, text))
                    except Exception as page_error:
                        _LOGGER.warning("Failed to extract text from page %d: %s", i, page_error)
                        continue
                
                if not scored_pages:
                    raise Exception("No relevant pages found in PDF")
                
                # Sort by score and combine top pages
                scored_pages.sort(key=lambda x: x[1], reverse=True)
                combined_text = "\n\n".join([text for _, _, text in scored_pages[:5]])
                _LOGGER.debug("Successfully extracted text from %d pages", len(scored_pages))
                break
                
            except Exception as e:
                last_error = e
                _LOGGER.warning("PDF parsing attempt %d failed: %s", attempt + 1, str(e))
                
                if attempt == 0:  # Only retry once for parsing
                    await asyncio.sleep(1)
        
        if combined_text is None:
            raise Exception(f"Failed to parse PDF: {last_error}")
        
        # Extract all data with error handling
        try:
            tariff_data = {
                "rates": self._extract_rates(combined_text),
                "tou_rates": self._extract_tou_rates(combined_text),
                "fixed_charges": self._extract_fixed_charges(combined_text),
                "tou_schedule": self._extract_tou_schedule(combined_text),
                "season_definitions": self._extract_season_definitions(combined_text),
                "effective_date": self._extract_effective_date(combined_text),
                "data_source": "pdf",
                "pdf_url": url,
            }
            
            _LOGGER.info("Successfully extracted tariff data from PDF")
            return tariff_data
            
        except Exception as e:
            _LOGGER.error("Failed to extract data from PDF text: %s", str(e))
            raise Exception(f"Data extraction failed: {e}")
    
    def get_data_source_type(self) -> str:
        """Return the type of data source."""
        return "pdf"
    
    def requires_file_download(self) -> bool:
        """PDF extractor requires file download."""
        return True
    
    async def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate extracted data."""
        if not data.get("rates") and not data.get("tou_rates"):
            return False, "No rates found in PDF"
        
        if not data.get("fixed_charges"):
            return False, "No fixed charges found in PDF"
        
        return True, None
    
    def _extract_rates(self, text: str) -> Dict[str, Any]:
        """Extract base rates from Xcel Energy PDF text."""
        rates = {}
        
        # Look for tiered rates first (Schedule R pattern)
        tier1_match = re.search(
            r"First\s+(\d+)\s+(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier1_match:
            rate_value = float(tier1_match.group(2))
            rates["summer"] = rate_value
            rates["winter"] = rate_value
            rates["tier_1"] = rate_value
            
        # Look for additional tiers
        tier2_match = re.search(
            r"All additional.*?(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier2_match:
            rates["tier_2"] = float(tier2_match.group(1))
        
        # Look for standard residential rate
        standard_match = re.search(
            r"(?:Energy Charge|Standard).*?per\s+(?:kWh|Kilowatt.hour)\s*\.+\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if standard_match and not rates:
            rate_value = float(standard_match.group(1))
            rates["standard"] = rate_value
            rates["summer"] = rate_value
            rates["winter"] = rate_value
            
        return rates
    
    def _extract_tou_rates(self, text: str) -> Dict[str, Any]:
        """Extract time-of-use rates from Xcel Energy PDF text."""
        tou_rates = {"summer": {}, "winter": {}}
        
        # Xcel-specific TOU patterns
        patterns = {
            "peak": [
                r"On-Peak.*?Period.*?\$(\d+\.?\d*)",
                r"Peak.*?Period.*?\$(\d+\.?\d*)",
                r"On.*Peak.*?(\d+\.?\d*)"
            ],
            "shoulder": [
                r"Shoulder.*?Period.*?\$(\d+\.?\d*)",
                r"Mid.*Peak.*?\$(\d+\.?\d*)"
            ],
            "off_peak": [
                r"Off-Peak.*?Period.*?\$(\d+\.?\d*)",
                r"Off.*Peak.*?(\d+\.?\d*)"
            ]
        }
        
        # Extract summer and winter rates
        seasons = ["Summer", "Winter"]
        for season in seasons:
            season_key = season.lower()
            season_section = self._extract_season_section(text, season)
            
            for period, pattern_list in patterns.items():
                for pattern in pattern_list:
                    match = re.search(pattern, season_section, re.IGNORECASE)
                    if match:
                        tou_rates[season_key][period] = float(match.group(1))
                        break
        
        return tou_rates
    
    def _extract_fixed_charges(self, text: str) -> Dict[str, Any]:
        """Extract fixed charges from Xcel Energy PDF text."""
        charges = {}
        
        # Xcel-specific patterns
        patterns = {
            "monthly_service": [
                r"Service and Facility Charge.*?\.+\s*\$(\d+\.?\d*)",
                r"Basic Service Charge.*?\.+\s*\$(\d+\.?\d*)",
                r"Customer Charge.*?\.+\s*\$(\d+\.?\d*)"
            ],
            "demand_charge": [
                r"Demand Charge.*?\.+\s*\$(\d+\.?\d*)",
                r"(?:kW|Kilowatt) Charge.*?\.+\s*\$(\d+\.?\d*)"
            ]
        }
        
        for charge_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    charges[charge_type] = float(match.group(1))
                    break
        
        # Default service charge if not found
        if "monthly_service" not in charges:
            charges["monthly_service"] = 15.0  # Reasonable default
        
        return charges
    
    def _extract_tou_schedule(self, text: str) -> Dict[str, Any]:
        """Extract TOU schedule from Xcel Energy PDF text."""
        schedule = {}
        
        # Look for Xcel-specific schedule definitions
        tou_section = re.search(
            r"DEFINITION OF BILLING PERIODS.*?(?=SCHEDULE|$)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        
        if tou_section:
            schedule_text = tou_section.group(0)
            
            # Extract peak hours
            peak_match = re.search(
                r"On-Peak.*?(\d{1,2}:\d{2}\s*(?:A\.M\.|P\.M\.)).*?(\d{1,2}:\d{2}\s*(?:A\.M\.|P\.M\.))",
                schedule_text,
                re.IGNORECASE
            )
            if peak_match:
                schedule["peak_hours"] = f"{peak_match.group(1)} - {peak_match.group(2)}"
            
            # Extract shoulder hours
            shoulder_match = re.search(
                r"Shoulder.*?(\d{1,2}:\d{2}\s*(?:A\.M\.|P\.M\.)).*?(\d{1,2}:\d{2}\s*(?:A\.M\.|P\.M\.))",
                schedule_text,
                re.IGNORECASE
            )
            if shoulder_match:
                schedule["shoulder_hours"] = f"{shoulder_match.group(1)} - {shoulder_match.group(2)}"
        
        return schedule
    
    def _extract_season_definitions(self, text: str) -> Dict[str, Any]:
        """Extract season definitions from Xcel Energy PDF text."""
        seasons = {}
        
        # Xcel typically uses June-September for summer
        summer_match = re.search(
            r"Summer.*?(?:June|May).*?(?:September|October)",
            text,
            re.IGNORECASE
        )
        if summer_match:
            seasons["summer_months"] = "6,7,8,9"  # Default Xcel pattern
        
        return seasons
    
    def _extract_effective_date(self, text: str) -> Optional[str]:
        """Extract effective date from Xcel Energy PDF text."""
        date_patterns = [
            r"Effective\s+(\w+\s+\d{1,2},\s+\d{4})",
            r"(?:In\s+)?Effect\s+(\w+\s+\d{1,2},\s+\d{4})",
            r"Effective Date:?\s*(\w+\s+\d{1,2},\s+\d{4})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _score_pdf_page(self, text: str, rate_schedule: str) -> int:
        """Score how relevant a PDF page is for Xcel Energy rate schedule."""
        score = 0
        text_lower = text.lower()
        
        # Xcel-specific scoring
        if "xcel energy" in text_lower:
            score += 20
        
        if rate_schedule.lower() in text_lower:
            score += 30
        
        if "schedule" in text_lower and rate_schedule.replace("_", "").replace("-", "") in text_lower:
            score += 25
        
        # Look for rate-specific keywords
        rate_keywords = {
            "residential": ["residential", "schedule r"],
            "residential_tou": ["time of use", "tou", "schedule re"],
            "commercial": ["commercial", "schedule c"]
        }
        
        keywords = rate_keywords.get(rate_schedule, [])
        for keyword in keywords:
            if keyword in text_lower:
                score += 15
        
        # Look for typical rate elements
        if "energy charge" in text_lower or "kilowatt" in text_lower:
            score += 10
        if "service charge" in text_lower or "facility charge" in text_lower:
            score += 10
        if "effective" in text_lower:
            score += 5
        
        return score
    
    def _extract_season_section(self, text: str, season: str) -> str:
        """Extract text section for a specific season."""
        pattern = rf"{season}.*?(?=(?:Winter|Summer)|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(0) if match else ""


class XcelEnergyRateCalculator(ProviderRateCalculator):
    """Xcel Energy specific rate calculator."""
    
    def calculate_current_rate(self, time: datetime, tariff_data: Dict[str, Any]) -> Optional[float]:
        """Calculate current Xcel Energy rate."""
        rates = tariff_data.get("rates", {})
        tou_rates = tariff_data.get("tou_rates", {})
        
        # Determine season
        is_summer = self.is_summer_season(time, tariff_data.get("season_definitions", {}))
        season = "summer" if is_summer else "winter"
        
        # If TOU rates available
        if tou_rates and tou_rates.get(season):
            period = self.get_tou_period(time, tariff_data)
            tou_season_rates = tou_rates[season]
            
            period_map = {
                "Peak": "peak",
                "Shoulder": "shoulder", 
                "Off-Peak": "off_peak"
            }
            
            rate_key = period_map.get(period, "off_peak")
            return tou_season_rates.get(rate_key)
        
        # Fall back to seasonal rates
        if rates:
            return rates.get(season) or rates.get("standard") or rates.get("tier_1")
        
        return None
    
    def get_tou_period(self, time: datetime, tariff_data: Dict[str, Any]) -> str:
        """Get current TOU period for Xcel Energy."""
        # Check if weekend or holiday
        if time.weekday() >= 5 or self.is_holiday(time.date(), {}):
            return "Off-Peak"
        
        # Xcel Energy TOU schedule (simplified)
        hour = time.hour
        
        if 15 <= hour < 19:  # 3 PM - 7 PM
            return "Peak"
        elif 13 <= hour < 15:  # 1 PM - 3 PM
            return "Shoulder"
        else:
            return "Off-Peak"
    
    def is_summer_season(self, time: datetime, season_config: Dict[str, Any]) -> bool:
        """Determine if time is in Xcel Energy summer season."""
        # Default Xcel summer: June-September
        summer_months = season_config.get("summer_months", "6,7,8,9")
        if isinstance(summer_months, str):
            months = [int(m.strip()) for m in summer_months.split(",")]
        else:
            months = summer_months
        
        return time.month in months
    
    def is_holiday(self, date: date, holiday_config: Dict[str, Any]) -> bool:
        """Check if date is a US federal holiday (Xcel Energy uses these)."""
        # Simplified holiday check - in practice would use a holiday library
        federal_holidays = {
            (1, 1): "New Year's Day",
            (7, 4): "Independence Day", 
            (12, 25): "Christmas Day"
        }
        
        return (date.month, date.day) in federal_holidays
    
    def get_all_current_rates(self, time: datetime, tariff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all current Xcel Energy rates and charges."""
        result = {}
        
        # Get base rates
        rates = tariff_data.get("rates", {})
        result.update(rates)
        
        # Get TOU rates if available and flatten by season
        tou_rates = tariff_data.get("tou_rates", {})
        if tou_rates:
            # Determine current season
            season = "summer" if self.is_summer_season(time, tariff_data.get("season_definitions", {})) else "winter"
            
            # Check if TOU rates are organized by season
            if season in tou_rates:
                # Seasonal TOU rates - use current season
                result["tou_rates"] = tou_rates[season]
            elif "peak" in tou_rates:
                # Direct TOU rates - use as-is
                result["tou_rates"] = tou_rates
            else:
                # Fallback to summer if available
                result["tou_rates"] = tou_rates.get("summer", tou_rates)
        
        # Get fixed charges
        fixed_charges = tariff_data.get("fixed_charges", {})
        result["fixed_charges"] = fixed_charges
        
        # Calculate additional charges (Xcel often has transmission/distribution charges)
        additional_charges = {}
        # In practice, would extract these from PDF or use configured values
        result["additional_charges"] = additional_charges
        result["total_additional"] = sum(additional_charges.values())
        
        return result


class XcelEnergyDataSource(ProviderDataSource):
    """Xcel Energy data source configuration."""
    
    BASE_URL = "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/"
    
    # Updated URL patterns based on current Xcel Energy website structure
    STATE_URLS = {
        "CO": f"{BASE_URL}PSCo_Electric_Entire_Tariff.pdf",  # Public Service Company of Colorado
        "MI": f"{BASE_URL}MPCO_Electric_Entire_Tariff.pdf",  # Michigan 
        "MN": f"{BASE_URL}NSP_MN_Electric_Entire_Tariff.pdf",  # Northern States Power - Minnesota
        "NM": f"{BASE_URL}SPS_NM_Electric_Entire_Tariff.pdf",  # Southwestern Public Service - New Mexico
        "ND": f"{BASE_URL}NSP_ND_Electric_Entire_Tariff.pdf",  # Northern States Power - North Dakota
        "SD": f"{BASE_URL}NSP_SD_Electric_Entire_Tariff.pdf",  # Northern States Power - South Dakota
        "TX": f"{BASE_URL}SPS_TX_Electric_Entire_Tariff.pdf",  # Southwestern Public Service - Texas
        "WI": f"{BASE_URL}NSP_WI_Electric_Entire_Tariff.pdf",  # Northern States Power - Wisconsin
    }
    
    # Alternative rate book URLs if tariff PDFs fail
    RATE_BOOK_URLS = {
        "CO": "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books",
        "MN": "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books",
    }
    
    def get_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        """Get PDF URL configuration for Xcel Energy.
        
        Note: Xcel Energy may have newer tariffs behind authentication on their
        rate books page. The public URLs may contain older versions.
        Consider using fallback rates for the most accurate current rates.
        """
        if service_type == "gas":
            # Gas URLs - replace Electric with Gas in the filename
            base_url = self.STATE_URLS.get(state, "")
            if base_url:
                url = base_url.replace("_Electric_", "_Gas_")
            else:
                url = ""
        else:
            url = self.STATE_URLS.get(state, "")
        
        return {
            "url": url,
            "type": "pdf",
            "note": "PDF may be outdated. Check rate books page for latest version."
        }
    
    def get_fallback_rates(self, state: str, service_type: str) -> Dict[str, Any]:
        """Get Xcel Energy fallback rates."""
        # Xcel Energy fallback rates by state
        # Updated for 2024/2025 with approximate 1.9% increase from 2024 rate case
        fallback_rates = {
            "CO": {
                "electric": {
                    "rates": {"summer": 0.07425, "winter": 0.05565},
                    "tou_rates": {
                        # Residential TOU Schedule RE-TOU
                        "summer": {"peak": 0.14124, "shoulder": 0.09677, "off_peak": 0.05231},
                        "winter": {"peak": 0.08893, "shoulder": 0.07062, "off_peak": 0.05231}
                    },
                    "fixed_charges": {"monthly_service": 13.13},  # Schedule R base charge
                    "tou_schedule": {
                        "peak": {"start": 15, "end": 19},  # 3 PM - 7 PM weekdays
                        "shoulder": {"start": 13, "end": 15}  # 1 PM - 3 PM weekdays
                    },
                    "season_definitions": {
                        "summer": [6, 7, 8, 9],
                        "winter": [1, 2, 3, 4, 5, 10, 11, 12]
                    },
                    "effective_date": "2024-05-01",
                    "note": "Rates effective May 1, 2024 following 2023 CO Electric Rate Review Phase II"
                },
                "gas": {
                    "rates": {"standard": 0.4523},
                    "fixed_charges": {"monthly_service": 8.85},
                    "effective_date": "2024-01-01"
                }
            },
            "MN": {
                "electric": {
                    "rates": {"summer": 0.08142, "winter": 0.06234},
                    "fixed_charges": {"monthly_service": 7.25},
                    "effective_date": "2024-01-01"
                }
            },
            # Add other states...
        }
        
        return fallback_rates.get(state, {}).get(service_type, {})
    
    def supports_real_time_rates(self) -> bool:
        """Xcel Energy doesn't support real-time rates via PDF."""
        return False
    
    def get_update_interval(self) -> timedelta:
        """PDFs should be checked daily at most."""
        return timedelta(days=1)


class XcelEnergyProvider(UtilityProvider):
    """Xcel Energy utility provider implementation."""
    
    def __init__(self):
        super().__init__("xcel_energy")
    
    @property
    def name(self) -> str:
        return "Xcel Energy"
    
    @property
    def short_name(self) -> str:
        return "Xcel"
    
    @property
    def supported_states(self) -> Dict[str, List[str]]:
        return {
            "electric": ["CO", "MI", "MN", "NM", "ND", "SD", "TX", "WI"],
            "gas": ["CO", "MN", "WI", "MI"]
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
        return XcelEnergyPDFExtractor()
    
    def _create_rate_calculator(self) -> ProviderRateCalculator:
        return XcelEnergyRateCalculator()
    
    def _create_data_source(self) -> ProviderDataSource:
        return XcelEnergyDataSource()