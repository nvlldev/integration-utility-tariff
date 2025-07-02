"""Enhanced Tariff Manager for Xcel Energy v2."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any

import aiohttp
import PyPDF2

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PDF_URLS, US_HOLIDAYS

_LOGGER = logging.getLogger(__name__)


class XcelTariffManager:
    """Enhanced manager for Xcel Energy tariff data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        state: str,
        service_type: str,
        rate_schedule: str = "residential",
        options: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the tariff manager."""
        self.hass = hass
        self.state = state
        self.service_type = service_type
        self._rate_schedule = rate_schedule
        self.options = options or {}
        
        # Cache paths
        self._cache_dir = Path(hass.config.path(f"custom_components/{DOMAIN}/cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._pdf_cache_path = self._cache_dir / f"{state}_{service_type}_tariff.pdf"
        self._data_cache_path = self._cache_dir / f"{state}_{service_type}_data.json"
        self._metadata_path = self._cache_dir / f"{state}_{service_type}_metadata.json"
        
        # Tariff data
        self._tariff_data: dict[str, Any] = {}
        self._pdf_hash: str | None = None
        self._last_pdf_check: datetime | None = None
        
        # Rate calculation cache
        self._rate_cache: dict[str, Any] = {}
        self._last_rate_cache_clear = dt_util.now()
        
        # Cached data will be loaded asynchronously during setup
        
    async def async_initialize(self) -> None:
        """Initialize the tariff manager asynchronously."""
        await self._load_cached_data()
        
    def _load_json_file(self, path: Path) -> dict[str, Any] | None:
        """Load JSON file synchronously for executor."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.error("Failed to load %s: %s", path, e)
            return None
    
    def _save_json_file(self, path: Path, data: dict[str, Any]) -> None:
        """Save JSON file synchronously for executor."""
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            _LOGGER.error("Failed to save %s: %s", path, e)
        
    @property
    def rate_schedule(self) -> str:
        """Get current rate schedule from options or default."""
        return self.options.get("rate_schedule", self._rate_schedule)
        
    def update_options(self, options: dict[str, Any]) -> None:
        """Update manager options."""
        self.options = options
        self._rate_cache.clear()  # Clear cache when options change
        
    async def _load_cached_data(self) -> None:
        """Load cached tariff data if available."""
        try:
            if self._data_cache_path.exists():
                loop = asyncio.get_event_loop()
                loaded_data = await loop.run_in_executor(
                    None, self._load_json_file, self._data_cache_path
                )
                if loaded_data:
                    self._tariff_data = loaded_data
                    _LOGGER.info("Loaded cached tariff data for %s %s (%d items)", 
                               self.state, self.service_type, len(loaded_data))
                else:
                    _LOGGER.warning("Cache file exists but contains no data")
                
            if self._metadata_path.exists():
                loop = asyncio.get_event_loop()
                metadata = await loop.run_in_executor(
                    None, self._load_json_file, self._metadata_path
                )
                if metadata:
                    self._pdf_hash = metadata.get("pdf_hash")
                    last_check = metadata.get("last_pdf_check")
                    if last_check:
                        self._last_pdf_check = datetime.fromisoformat(last_check)
                        
            # If no cached data was loaded, ensure we have fallback rates
            if not self._tariff_data:
                _LOGGER.info("No cached data found, initializing with fallback rates")
                self._tariff_data = self._get_fallback_rates()
                await self._save_cached_data()
                
        except Exception as e:
            _LOGGER.warning("Failed to load cached data: %s", e)
            # Initialize with fallback rates on error
            self._tariff_data = self._get_fallback_rates()
            
    async def _save_cached_data(self) -> None:
        """Save tariff data to cache."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._save_json_file, self._data_cache_path, self._tariff_data
            )
                
            metadata = {
                "pdf_hash": self._pdf_hash,
                "last_pdf_check": self._last_pdf_check.isoformat() if self._last_pdf_check else None,
                "rate_schedule": self.rate_schedule,
            }
            await loop.run_in_executor(
                None, self._save_json_file, self._metadata_path, metadata
            )
                
            _LOGGER.debug("Saved tariff data to cache")
        except Exception as e:
            _LOGGER.error("Failed to save cache: %s", e)
            
    async def async_update_tariffs(self) -> dict[str, Any]:
        """Update tariff data from Xcel Energy."""
        now = dt_util.now()
        
        # Check if we should update based on frequency setting
        update_frequency = self.options.get("update_frequency", "weekly")
        if self._last_pdf_check:
            if update_frequency == "daily":
                if (now - self._last_pdf_check).days < 1:
                    _LOGGER.debug("Skipping update, already checked today")
                    return self._tariff_data if self._tariff_data else self._get_fallback_rates()
            else:  # weekly
                if (now - self._last_pdf_check).days < 7:
                    _LOGGER.debug("Skipping update, checked %d days ago", 
                                (now - self._last_pdf_check).days)
                    return self._tariff_data if self._tariff_data else self._get_fallback_rates()
        
        # Download and parse PDF
        pdf_updated = await self._download_pdf()
        
        if pdf_updated:
            await self._parse_pdf()
            await self._save_cached_data()
        
        # Always ensure we have at least fallback data
        if not self._tariff_data:
            _LOGGER.warning("No PDF data available, using fallback rates")
            self._tariff_data = self._get_fallback_rates()
            await self._save_cached_data()  # Save fallback data to cache
                
        self._last_pdf_check = now
        return self._tariff_data
        
    async def _download_pdf(self) -> bool:
        """Download PDF if updated."""
        urls = PDF_URLS.get(self.state, {})
        if self.service_type not in urls:
            _LOGGER.warning("No PDF URL configured for state=%s, service_type=%s", self.state, self.service_type)
            _LOGGER.debug("Available URLs: %s", urls)
            return False
            
        url = urls[self.service_type]
        _LOGGER.info("Attempting to download PDF from: %s", url)
        
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            
            # First check if PDF has changed
            async with session.head(url) as response:
                if response.status != 200:
                    _LOGGER.error("Failed to check PDF: %s", response.status)
                    return False
                    
                # Check etag or last-modified
                etag = response.headers.get("etag")
                last_modified = response.headers.get("last-modified")
                
            # Download PDF
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error("Failed to download PDF: %s", response.status)
                    return False
                    
                pdf_content = await response.read()
                
                # Check if content has changed
                new_hash = hashlib.sha256(pdf_content).hexdigest()
                if new_hash == self._pdf_hash:
                    _LOGGER.debug("PDF has not changed")
                    return False
                    
                # Save new PDF
                with open(self._pdf_cache_path, "wb") as f:
                    f.write(pdf_content)
                    
                self._pdf_hash = new_hash
                self._tariff_data["pdf_url"] = url
                self._tariff_data["pdf_hash"] = new_hash
                
                _LOGGER.info("Downloaded updated PDF for %s %s", self.state, self.service_type)
                return True
                
        except aiohttp.ClientError as e:
            _LOGGER.error("Failed to download PDF: %s", e)
            
            # Create repair issue if we have a config entry
            if hasattr(self, '_config_entry') and self._config_entry:
                from .repairs import async_create_repair_issue
                async_create_repair_issue(
                    self.hass,
                    self._config_entry,
                    "pdf_error",
                    f"Network error: {e}"
                )
            
            return False
        except Exception as e:
            _LOGGER.error("Unexpected error downloading PDF: %s", e)
            
            # Create repair issue if we have a config entry
            if hasattr(self, '_config_entry') and self._config_entry:
                from .repairs import async_create_repair_issue
                async_create_repair_issue(
                    self.hass,
                    self._config_entry,
                    "pdf_error",
                    f"Download error: {e}"
                )
            
            return False
            
    async def _parse_pdf(self) -> None:
        """Parse the PDF with enhanced extraction."""
        if not self._pdf_cache_path.exists():
            _LOGGER.error("PDF file not found at %s", self._pdf_cache_path)
            return
            
        try:
            # Run PDF parsing in executor to avoid blocking
            loop = asyncio.get_event_loop()
            extracted_data = await loop.run_in_executor(
                None, self._extract_all_data_from_pdf
            )
            
            # Check if we got any meaningful data
            if not extracted_data or not any(extracted_data.values()):
                _LOGGER.warning("No data extracted from PDF, will use fallback rates")
                return
            
            # Merge with existing data
            self._tariff_data.update(extracted_data)
            self._tariff_data["last_updated"] = dt_util.now().isoformat()
            self._tariff_data["extraction_method"] = "enhanced_v2"
            
            # If no rates were extracted, merge with fallback rates
            if not self._tariff_data.get("rates"):
                _LOGGER.warning("No rates extracted from PDF, merging with fallback rates")
                fallback = self._get_fallback_rates()
                self._tariff_data["rates"] = fallback.get("rates", {})
                if not self._tariff_data.get("tou_rates"):
                    self._tariff_data["tou_rates"] = fallback.get("tou_rates", {})
                if not self._tariff_data.get("fixed_charges"):
                    self._tariff_data["fixed_charges"] = fallback.get("fixed_charges", {})
            
            _LOGGER.info("Successfully parsed PDF with %d data points", 
                        sum(1 for v in extracted_data.values() if v))
            
        except Exception as e:
            _LOGGER.error("Failed to parse PDF: %s", e, exc_info=True)
            
            # Create repair issue if we have a config entry
            if hasattr(self, '_config_entry') and self._config_entry:
                from .repairs import async_create_repair_issue
                async_create_repair_issue(
                    self.hass,
                    self._config_entry,
                    "pdf_error",
                    str(e)
                )
            
    def _extract_all_data_from_pdf(self) -> dict[str, Any]:
        """Extract all available data from PDF."""
        extracted = {
            "rates": {},
            "tou_rates": {},
            "tou_schedule": {},
            "fixed_charges": {},
            "demand_charges": {},
            "additional_charges": {},
            "rate_details": {},
            "riders": {},
            "credits": {},
        }
        
        try:
            with open(self._pdf_cache_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract text from relevant pages
                text = self._extract_optimized_text(pdf_reader)
                
                # Run all extractors
                extracted["rates"] = self._extract_base_rates(text)
                extracted["tou_rates"] = self._extract_tou_rates(text)
                extracted["tou_schedule"] = self._extract_tou_schedule(text)
                extracted["fixed_charges"] = self._extract_fixed_charges(text)
                extracted["additional_charges"] = self._extract_additional_charges(text)
                extracted["rate_details"] = self._extract_rate_details(text)
                extracted["riders"] = self._extract_riders(text)
                extracted["credits"] = self._extract_credits(text)
                
                # Add metadata
                extracted["rate_schedule_name"] = self._extract_schedule_name(text)
                extracted["effective_date"] = self._extract_effective_date(text)
                extracted["season_definitions"] = self._extract_season_definitions(text)
                
        except Exception as e:
            _LOGGER.error("PDF extraction failed: %s", e)
            
        return extracted
        
    def _extract_optimized_text(self, pdf_reader: PyPDF2.PdfReader) -> str:
        """Extract text from PDF with optimizations."""
        # Smart page selection based on rate schedule
        relevant_pages = self._find_relevant_pages(pdf_reader)
        
        text_parts = []
        for page_num in relevant_pages[:30]:  # Limit to 30 most relevant pages
            try:
                page = pdf_reader.pages[page_num]
                text_parts.append(page.extract_text())
            except Exception as e:
                _LOGGER.warning("Failed to extract page %d: %s", page_num, e)
                
        return "\n".join(text_parts)
        
    def _find_relevant_pages(self, pdf_reader: PyPDF2.PdfReader) -> list[int]:
        """Find pages most likely to contain rate information."""
        # Specific schedule names to look for
        schedule_map = {
            "residential": ["SCHEDULE R", "Residential General"],
            "residential_tou": ["SCHEDULE RE-TOU", "RE-TOU", "Residential Energy Time-of-Use"],
            "residential_ev": ["SCHEDULE REV", "EV", "Electric Vehicle"],
            "commercial": ["SCHEDULE C", "Commercial"],
        }
        
        # Get specific schedule names for this rate schedule
        schedule_names = schedule_map.get(self.rate_schedule, [self.rate_schedule.upper()])
        
        # Additional keywords
        keywords = ["Monthly Rate", "Energy Charge", "Service and Facility Charge", "per kWh"]
        if "tou" in self.rate_schedule.lower():
            keywords.extend(["On-peak", "Off-Peak", "Shoulder", "Summer Season", "Winter Season"])
            
        page_scores = {}
        
        # Score pages with emphasis on schedule name matches
        for i in range(min(100, len(pdf_reader.pages))):
            try:
                text = pdf_reader.pages[i].extract_text()
                score = 0
                
                # High score for exact schedule name match
                for schedule_name in schedule_names:
                    if schedule_name in text:
                        score += 100
                        
                # Additional score for rate-related keywords
                score += sum(text.count(keyword) for keyword in keywords)
                
                # Bonus for pages with actual rate values (numbers followed by ¢)
                if re.search(r"\d+\.?\d*\s*[¢c]", text):
                    score += 50
                    
                if score > 0:
                    page_scores[i] = score
                    _LOGGER.debug("Page %d score: %d", i+1, score)
                    
            except Exception as e:
                _LOGGER.debug("Error scoring page %d: %s", i+1, e)
                continue
                
        # Return pages sorted by relevance
        sorted_pages = sorted(page_scores.keys(), key=page_scores.get, reverse=True)
        _LOGGER.debug("Top relevant pages: %s", [p+1 for p in sorted_pages[:5]])
        return sorted_pages
        
    def _extract_base_rates(self, text: str) -> dict[str, float]:
        """Extract base energy rates."""
        rates = {}
        
        # Look for tiered rates first (Schedule R pattern)
        tier1_match = re.search(
            r"First\s+(\d+)\s+(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier1_match:
            # Store the first tier rate as both summer and winter for residential
            # The PDF values are already in dollars (e.g., 0.06237 = $0.06237/kWh)
            rate_value = float(tier1_match.group(2))
            rates["summer"] = rate_value
            rates["winter"] = rate_value
            rates["tier_1"] = rate_value
            _LOGGER.debug("Found tier 1 rate: $%s/kWh", rate_value)
            
        # Look for tier 2 rates
        tier2_match = re.search(
            r"(?:Over|Excess over)\s+(\d+)\s+(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier2_match:
            # The PDF values are already in dollars
            rates["tier_2"] = float(tier2_match.group(2))
            _LOGGER.debug("Found tier 2 rate: $%s/kWh", tier2_match.group(2))
            
        # If no tiered rates, look for seasonal rates
        if not rates:
            # Summer rates
            summer_match = re.search(
                r"Summer Season.*?(?:All\s+)?(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if summer_match:
                rates["summer"] = float(summer_match.group(1))
                _LOGGER.debug("Found summer rate: $%s/kWh", summer_match.group(1))
                
            # Winter rates
            winter_match = re.search(
                r"Winter Season.*?(?:All\s+)?(?:Kilowatt-Hours|kWh).*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if winter_match:
                rates["winter"] = float(winter_match.group(1))
                _LOGGER.debug("Found winter rate: $%s/kWh", winter_match.group(1))
                
        # If still no rates, try general energy charge pattern
        if not rates:
            energy_match = re.search(
                r"Energy Charge.*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if energy_match:
                rates["standard"] = float(energy_match.group(1))
                _LOGGER.debug("Found standard energy rate: $%s/kWh", energy_match.group(1))
                
        return rates
        
    def _extract_tou_rates(self, text: str) -> dict[str, dict[str, float]]:
        """Extract time-of-use rates."""
        tou_rates = {"summer": {}, "winter": {}}
        
        # Improved patterns that account for dots between label and value
        patterns = {
            "peak": r"On-peak Energy Charge.*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
            "shoulder": r"Shoulder Energy Charge.*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
            "off_peak": r"Off-Peak Energy Charge.*?per\s+kWh\s*\.+\s*(\d+\.?\d*)",
        }
        
        # Look for seasonal sections
        summer_section = re.search(
            r"Summer Season.*?(?=Winter Season|$)", 
            text, 
            re.DOTALL | re.IGNORECASE
        )
        
        if summer_section:
            summer_text = summer_section.group(0)
            for period, pattern in patterns.items():
                match = re.search(pattern, summer_text, re.IGNORECASE | re.DOTALL)
                if match:
                    # PDF values are already in dollars
                    tou_rates["summer"][period] = float(match.group(1))
                    _LOGGER.debug("Found summer %s rate: $%s/kWh", period, match.group(1))
                    
        # Look for winter section
        winter_section = re.search(
            r"Winter Season.*?(?=GENERAL|SPECIAL|MONTHLY RATE|$)", 
            text, 
            re.DOTALL | re.IGNORECASE
        )
        
        if winter_section:
            winter_text = winter_section.group(0)
            for period, pattern in patterns.items():
                match = re.search(pattern, winter_text, re.IGNORECASE | re.DOTALL)
                if match:
                    # PDF values are already in dollars
                    tou_rates["winter"][period] = float(match.group(1))
                    _LOGGER.debug("Found winter %s rate: $%s/kWh", period, match.group(1))
                    
        return tou_rates
        
    def _extract_tou_schedule(self, text: str) -> dict[str, Any]:
        """Extract TOU schedule information."""
        schedule = {
            "summer": {},
            "winter": {},
            "season_months": {},
            "holidays": [],
        }
        
        # Extract time periods
        time_patterns = {
            "peak": r"(?:On-Peak|Peak)[:\s]+.*?(\d{1,2}):?(\d{2})?\s*(AM|PM|a\.m\.|p\.m\.)\s*[-–to]+\s*(\d{1,2}):?(\d{2})?\s*(AM|PM|a\.m\.|p\.m\.)",
            "shoulder": r"Shoulder[:\s]+.*?(\d{1,2}):?(\d{2})?\s*(AM|PM|a\.m\.|p\.m\.)\s*[-–to]+\s*(\d{1,2}):?(\d{2})?\s*(AM|PM|a\.m\.|p\.m\.)",
        }
        
        for period, pattern in time_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_hour = int(match.group(1))
                start_min = int(match.group(2)) if match.group(2) else 0
                start_period = match.group(3).upper()
                end_hour = int(match.group(4))
                end_min = int(match.group(5)) if match.group(5) else 0
                end_period = match.group(6).upper()
                
                # Convert to 24-hour format
                if "P" in start_period and start_hour != 12:
                    start_hour += 12
                elif "A" in start_period and start_hour == 12:
                    start_hour = 0
                if "P" in end_period and end_hour != 12:
                    end_hour += 12
                elif "A" in end_period and end_hour == 12:
                    end_hour = 0
                    
                schedule["summer"][f"{period}_hours"] = f"{start_hour}:{start_min:02d} - {end_hour}:{end_min:02d}"
                schedule["winter"][f"{period}_hours"] = f"{start_hour}:{start_min:02d} - {end_hour}:{end_min:02d}"
                
        # Extract season definitions
        season_match = re.search(r"Summer Season.*?\(([^)]+)\)", text, re.IGNORECASE)
        if season_match:
            months_text = season_match.group(1)
            # Parse months (e.g., "June 1 through September 30")
            if "June" in months_text:
                schedule["season_months"]["summer"] = [6, 7, 8, 9]
                schedule["season_months"]["winter"] = [1, 2, 3, 4, 5, 10, 11, 12]
                
        return schedule
        
    def _extract_fixed_charges(self, text: str) -> dict[str, float]:
        """Extract fixed monthly charges."""
        charges = {}
        
        # Improved patterns that account for dots between label and value
        patterns = {
            "monthly_service": [
                r"Service and Facility Charge:\s*\.+\s*\$?\s*(\d+\.?\d*)",
                r"Service.*?Charge.*?\.+\s*\$?\s*(\d+\.?\d*)",
                r"Customer.*?Charge.*?\.+\s*\$?\s*(\d+\.?\d*)",
            ],
            "meter_charge": [
                r"(?:Production|Load) Meter Charge:?\s*\.+\s*\$?\s*(\d+\.?\d*)",
                r"Meter.*?Charge.*?\.+\s*\$?\s*(\d+\.?\d*)",
            ],
        }
        
        for charge_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    charges[charge_type] = float(match.group(1))
                    _LOGGER.debug("Found %s: $%s", charge_type, match.group(1))
                    break  # Use first match
                
        # If we didn't find monthly_service but found something else, use it
        if not charges.get("monthly_service") and charges:
            charges["monthly_service"] = next(iter(charges.values()))
                
        return charges
        
    def _extract_additional_charges(self, text: str) -> dict[str, float]:
        """Extract additional per-kWh charges."""
        charges = {}
        
        # Look for adjustment clauses, riders, etc.
        patterns = {
            "fuel_adjustment": r"Fuel.*?Adjustment.*?(\d+\.?\d*)\s*[¢c]",
            "renewable_energy": r"Renewable.*?Energy.*?(\d+\.?\d*)\s*[¢c]",
            "transmission": r"Transmission.*?Cost.*?(\d+\.?\d*)\s*[¢c]",
            "distribution": r"Distribution.*?Cost.*?(\d+\.?\d*)\s*[¢c]",
        }
        
        for charge_type, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                charges[charge_type] = float(match.group(1)) / 100  # Convert cents to dollars
                
        return charges
        
    def _extract_rate_details(self, text: str) -> dict[str, Any]:
        """Extract additional rate details."""
        details = {}
        
        # Power factor
        pf_match = re.search(r"Power Factor.*?(\d+\.?\d*)%", text, re.IGNORECASE)
        if pf_match:
            details["power_factor_threshold"] = float(pf_match.group(1))
            
        # Minimum bill
        min_bill_match = re.search(r"Minimum.*?Bill.*?\$\s*(\d+\.?\d*)", text, re.IGNORECASE)
        if min_bill_match:
            details["minimum_bill"] = float(min_bill_match.group(1))
            
        return details
        
    def _extract_riders(self, text: str) -> dict[str, float]:
        """Extract rider charges."""
        riders = {}
        
        # Look for specific riders
        rider_section = re.search(r"RIDERS.*?(?:GENERAL|SPECIAL|$)", text, re.DOTALL | re.IGNORECASE)
        if rider_section:
            # Extract individual riders
            pass
            
        return riders
        
    def _extract_credits(self, text: str) -> dict[str, float]:
        """Extract available credits."""
        credits = {}
        
        # Look for solar credits, etc.
        patterns = {
            "solar_credit": r"Solar.*?Credit.*?(\d+\.?\d*)\s*[¢c]",
            "net_metering": r"Net Metering.*?(\d+\.?\d*)\s*[¢c]",
        }
        
        for credit_type, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                credits[credit_type] = float(match.group(1)) / 100
                
        return credits
        
    def _extract_schedule_name(self, text: str) -> str | None:
        """Extract the rate schedule name."""
        match = re.search(r"SCHEDULE\s+([A-Z0-9\-]+)", text)
        if match:
            return match.group(1)
        return None
        
    def _extract_effective_date(self, text: str) -> str | None:
        """Extract the effective date."""
        match = re.search(r"Effective.*?(\w+\s+\d+,?\s+\d{4})", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
        
    def _extract_season_definitions(self, text: str) -> dict[str, str]:
        """Extract season definitions."""
        seasons = {}
        
        patterns = {
            "summer": r"Summer Season.*?\(([^)]+)\)",
            "winter": r"Winter Season.*?\(([^)]+)\)",
        }
        
        for season, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                seasons[season] = match.group(1)
                
        return seasons
        
    def get_current_rate(self) -> float | None:
        """Get the current electricity rate based on time and season."""
        # Ensure we have data - use tariff data if available, otherwise fallback
        if not self._tariff_data:
            self._tariff_data = self._get_fallback_rates()
            _LOGGER.info("Using fallback rates for %s %s", self.state, self.service_type)
            
        if not self._tariff_data:
            _LOGGER.error("No tariff data available and fallback rates failed")
            return None
            
        _LOGGER.debug("Rate schedule: %s, Tariff data keys: %s", 
                     self.rate_schedule, list(self._tariff_data.keys()))
            
        now = dt_util.now()
        
        # Clear cache every hour
        if (now - self._last_rate_cache_clear).seconds > 3600:
            self._rate_cache.clear()
            self._last_rate_cache_clear = now
            
        # Check cache
        cache_key = f"{now.hour}_{now.weekday()}_{now.month}_{now.day}"
        if cache_key in self._rate_cache:
            return self._rate_cache[cache_key]
            
        # Use the data we have
        data = self._tariff_data
        
        # Determine if summer/winter
        is_summer = self.is_summer_season(now)
        
        # Get TOU rate if applicable
        if "tou" in self.rate_schedule and data.get("tou_rates"):
            rate = self._get_tou_rate(now, is_summer, data)
            _LOGGER.debug("TOU rate returned: %s", rate)
        else:
            rate = self._get_flat_rate(is_summer, data)
            _LOGGER.debug("Flat rate returned: %s", rate)
            
        # Add additional charges if configured
        if self.options.get("include_additional_charges", True):
            additional = sum(data.get("additional_charges", {}).values())
            if additional and rate:
                rate += additional
                
        # Cache the result
        if rate is not None:
            self._rate_cache[cache_key] = rate
            
        return rate
        
    def is_summer_season(self, now: datetime) -> bool:
        """Determine if current date is in summer season."""
        # Check for custom summer months from options
        summer_months_str = self.options.get("summer_months", "6,7,8,9")
        try:
            summer_months = [int(m.strip()) for m in summer_months_str.split(",")]
        except ValueError:
            summer_months = [6, 7, 8, 9]  # Default
            
        # Check extracted season definitions first
        if self._tariff_data:
            season_months = self._tariff_data.get("tou_schedule", {}).get("season_months", {})
            if season_months.get("summer"):
                return now.month in season_months["summer"]
                
        # Use configured or default months
        return now.month in summer_months
        
    def is_holiday(self, date) -> bool:
        """Check if date is a holiday."""
        # Check custom holidays from options
        custom_holidays = self.options.get("custom_holidays", [])
        if custom_holidays:
            for holiday in custom_holidays:
                if holiday == date.isoformat():
                    return True
                    
        # Check standard US holidays
        return date in US_HOLIDAYS
        
    def get_current_tou_period(self) -> str:
        """Get current TOU period (Peak, Shoulder, Off-Peak)."""
        if "tou" not in self.rate_schedule:
            return "N/A"
            
        now = dt_util.now()
        
        # Check custom schedule from options
        if self._use_custom_schedule():
            return self._get_custom_tou_period(now)
            
        # Use extracted or default schedule
        is_summer = self.is_summer_season(now)
        is_weekday = now.weekday() < 5
        is_holiday = self.is_holiday(now.date())
        
        if not is_weekday or is_holiday:
            return "Off-Peak"
            
        hour = now.hour
        
        # Default Colorado RE-TOU schedule
        if 15 <= hour < 19:  # 3 PM - 7 PM
            return "Peak"
        elif 13 <= hour < 15:  # 1 PM - 3 PM
            return "Shoulder"
        else:
            return "Off-Peak"
            
    def _use_custom_schedule(self) -> bool:
        """Check if custom TOU schedule is configured."""
        return all(key in self.options for key in ["peak_start", "peak_end"])
        
    def _get_custom_tou_period(self, now: datetime) -> str:
        """Get TOU period based on custom schedule."""
        if now.weekday() >= 5 or self.is_holiday(now.date()):
            return "Off-Peak"
            
        current_time = now.strftime("%H:%M")
        
        # Parse custom times
        peak_start = self.options.get("peak_start", "15:00")
        peak_end = self.options.get("peak_end", "19:00")
        shoulder_start = self.options.get("shoulder_start", "13:00")
        shoulder_end = self.options.get("shoulder_end", "15:00")
        
        if shoulder_start <= current_time < shoulder_end:
            return "Shoulder"
        elif peak_start <= current_time < peak_end:
            return "Peak"
        else:
            return "Off-Peak"
            
    def _get_tou_rate(self, now: datetime, is_summer: bool, data: dict) -> float | None:
        """Get current TOU rate based on time of day."""
        season = "summer" if is_summer else "winter"
        season_rates = data.get("tou_rates", {}).get(season, {})
        _LOGGER.debug("Getting TOU rate - season: %s, season_rates: %s", season, season_rates)
        
        if not season_rates:
            return None
            
        period = self.get_current_tou_period()
        
        period_map = {
            "Peak": "peak",
            "Shoulder": "shoulder", 
            "Off-Peak": "off_peak"
        }
        
        rate_key = period_map.get(period, "off_peak")
        rate = season_rates.get(rate_key)
        _LOGGER.debug("TOU period: %s, rate_key: %s, rate: %s", period, rate_key, rate)
        
        return rate
        
    def _get_flat_rate(self, is_summer: bool, data: dict) -> float | None:
        """Get current flat rate."""
        rates = data.get("rates", {})
        _LOGGER.debug("Getting flat rate - is_summer: %s, rates: %s", is_summer, rates)
        
        if is_summer and "summer" in rates:
            return rates["summer"]
        elif not is_summer and "winter" in rates:
            return rates["winter"]
        else:
            return rates.get("standard") or rates.get("tier_1")
            
    def get_all_current_rates(self) -> dict[str, Any]:
        """Get all applicable rates for current time."""
        now = dt_util.now()
        is_summer = self.is_summer_season(now)
        season = "summer" if is_summer else "winter"
        
        # Get data source
        data = self._tariff_data if self._tariff_data else self._get_fallback_rates()
        
        all_rates = {
            "base_rate": self.get_current_rate(),
            "season": season,
            "data_source": "pdf" if self._tariff_data else "fallback",
        }
        
        # Add fixed charges
        if data.get("fixed_charges"):
            all_rates["fixed_charges"] = data["fixed_charges"]
            
        # Add TOU rates if applicable
        if "tou" in self.rate_schedule and data.get("tou_rates"):
            all_rates["tou_rates"] = data["tou_rates"].get(season, {})
            all_rates["current_period"] = self.get_current_tou_period()
            
        # Add additional charges
        if data.get("additional_charges"):
            all_rates["additional_charges"] = data["additional_charges"]
            all_rates["total_additional"] = sum(data["additional_charges"].values())
            
        # Add riders and credits
        if data.get("riders"):
            all_rates["riders"] = data["riders"]
        if data.get("credits"):
            all_rates["credits"] = data["credits"]
            
        return all_rates
        
    def get_rate_details(self) -> dict[str, Any]:
        """Get comprehensive rate details."""
        data = self._tariff_data if self._tariff_data else {}
        
        details = data.get("rate_details", {})
        details["rate_schedule_name"] = data.get("rate_schedule_name") or self.rate_schedule
        details["effective_date"] = data.get("effective_date")
        details["data_source"] = "pdf" if self._tariff_data else "fallback"
        
        if data.get("season_definitions"):
            details["season_definitions"] = data["season_definitions"]
            
        return details
        
    def _get_fallback_rates(self) -> dict[str, Any]:
        """Get fallback rates when PDF parsing fails."""
        _LOGGER.warning("Using fallback rates for %s %s", self.state, self.service_type)
        
        # Comprehensive fallback rates
        fallback_data = {
            "last_updated": dt_util.now().isoformat(),
            "rates": {},
            "tou_rates": {},
            "fixed_charges": {},
            "tou_schedule": {},
        }
        
        if self.service_type == "electric":
            if self.state == "CO":
                # Colorado actual rates from PDF extraction
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.13861, "off_peak": 0.05134, "shoulder": 0.09497},
                        "winter": {"peak": 0.08727, "off_peak": 0.05134, "shoulder": 0.06930}
                    }
                    fallback_data["tou_schedule"] = {
                        "summer": {
                            "peak_hours": "15:00 - 19:00",
                            "shoulder_hours": "13:00 - 15:00",
                        },
                        "winter": {
                            "peak_hours": "15:00 - 19:00",
                            "shoulder_hours": "13:00 - 15:00",
                        },
                        "season_months": {
                            "summer": [6, 7, 8, 9],
                            "winter": [1, 2, 3, 4, 5, 10, 11, 12]
                        }
                    }
                else:
                    fallback_data["rates"] = {"summer": 0.07287, "winter": 0.05461}
                fallback_data["fixed_charges"] = {"monthly_service": 5.59}
                
            elif self.state == "MN":
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.22, "off_peak": 0.07, "shoulder": 0.11},
                        "winter": {"peak": 0.19, "off_peak": 0.07, "shoulder": 0.10}
                    }
                else:
                    fallback_data["rates"] = {"standard": 0.11}
                fallback_data["fixed_charges"] = {"monthly_service": 10.50}
                
            elif self.state == "WI":
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.23, "off_peak": 0.08},
                        "winter": {"peak": 0.20, "off_peak": 0.08}
                    }
                else:
                    fallback_data["rates"] = {"summer": 0.13, "winter": 0.11}
                fallback_data["fixed_charges"] = {"monthly_service": 11.25}
                
            elif self.state == "MI":
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.24, "off_peak": 0.09},
                        "winter": {"peak": 0.21, "off_peak": 0.09}
                    }
                else:
                    fallback_data["rates"] = {"summer": 0.14, "winter": 0.12}
                fallback_data["fixed_charges"] = {"monthly_service": 11.95}
                
            elif self.state == "NM":
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.20, "off_peak": 0.06},
                        "winter": {"peak": 0.17, "off_peak": 0.06}
                    }
                else:
                    fallback_data["rates"] = {"summer": 0.11, "winter": 0.09}
                fallback_data["fixed_charges"] = {"monthly_service": 10.00}
                
            elif self.state == "TX":
                if "tou" in self.rate_schedule:
                    fallback_data["tou_rates"] = {
                        "summer": {"peak": 0.25, "off_peak": 0.09},
                        "winter": {"peak": 0.22, "off_peak": 0.09}
                    }
                else:
                    fallback_data["rates"] = {"summer": 0.13, "winter": 0.11}
                fallback_data["fixed_charges"] = {"monthly_service": 10.25}
                
            elif self.state == "ND":
                fallback_data["rates"] = {"standard": 0.10}
                fallback_data["fixed_charges"] = {"monthly_service": 9.50}
                
            elif self.state == "SD":
                fallback_data["rates"] = {"standard": 0.11}
                fallback_data["fixed_charges"] = {"monthly_service": 9.75}
                
            else:
                # Generic fallback
                fallback_data["rates"] = {"standard": 0.12}
                fallback_data["fixed_charges"] = {"monthly_service": 12.00}
                
        elif self.service_type == "gas":
            # Gas rates by state
            gas_rates = {
                "CO": {"rate": 0.75, "service": 12.00},
                "MN": {"rate": 0.80, "service": 14.00},
                "WI": {"rate": 0.78, "service": 13.75},
                "MI": {"rate": 0.60, "service": 11.50},
            }
            
            if self.state in gas_rates:
                fallback_data["rates"] = {"standard": gas_rates[self.state]["rate"]}
                fallback_data["fixed_charges"] = {"monthly_service": gas_rates[self.state]["service"]}
            else:
                fallback_data["rates"] = {"standard": 0.75}
                fallback_data["fixed_charges"] = {"monthly_service": 12.50}
                
        return fallback_data
        
    def clear_cache(self) -> None:
        """Clear all caches."""
        self._rate_cache.clear()
        self._tariff_data.clear()
        self._pdf_hash = None
        self._last_pdf_check = None
        
        # Delete cache files
        for path in [self._pdf_cache_path, self._data_cache_path, self._metadata_path]:
            if path.exists():
                path.unlink()
                
        _LOGGER.info("Cleared all caches for %s %s", self.state, self.service_type)