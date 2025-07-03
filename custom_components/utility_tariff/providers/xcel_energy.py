"""Xcel Energy provider implementation."""

import re
import logging
import asyncio
import json
import hashlib
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
import aiofiles
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
        service_type = kwargs.get("service_type", "electric")
        use_bundled_fallback = kwargs.get("use_bundled_fallback", True)
        
        # First, check if we have URL sources in metadata that should be tried
        url_sources = await self._get_url_sources(service_type)
        
        # Check for bundled PDF first
        bundled_pdf_info = None
        bundled_pdf_content = None
        if use_bundled_fallback:
            bundled_pdf_info, bundled_pdf_content = await self._get_bundled_pdf(service_type)
            if bundled_pdf_content:
                _LOGGER.info("Found bundled PDF for %s service", service_type)
        
        # Try URL sources from metadata if no explicit URL provided
        if not url and url_sources:
            _LOGGER.info("Found %d URL source(s) in metadata for %s service", len(url_sources), service_type)
            # Use the first (most recent) URL source
            url = url_sources[0]["source"]
            _LOGGER.info("Using URL from metadata: %s", url)
        
        # Try to download the PDF if URL provided
        pdf_content = None
        pdf_source = "downloaded"
        last_error = None
        
        if url:
            # Retry configuration
            max_retries = 3
            retry_delay = 2
            
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
        
        # Use bundled PDF as fallback if download failed
        if pdf_content is None and bundled_pdf_content:
            _LOGGER.warning("Download failed, using bundled PDF as fallback")
            pdf_content = bundled_pdf_content
            pdf_source = "bundled"
            url = f"bundled://{bundled_pdf_info['filename']}"
        elif pdf_content is None:
            raise Exception(f"Failed to download PDF and no bundled fallback available: {last_error}")
        
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
                "pdf_source": pdf_source,
            }
            
            # Add bundled PDF metadata if using bundled
            if pdf_source == "bundled" and bundled_pdf_info:
                tariff_data["bundled_pdf_info"] = bundled_pdf_info
                tariff_data["pdf_hash"] = hashlib.md5(pdf_content).hexdigest()
            
            _LOGGER.info("Successfully extracted tariff data from %s PDF", pdf_source)
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
        
        # Check if this is a summary table format (April 2025 format)
        if "Total Monthly Rate" in text and "Residential ( R)" in text:
            # This is a summary table - extract from Charge Amount column (first numeric value)
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'Residential ( R)' in line or 'Residential (R)' in line:
                    # Look for energy rates in following lines
                    for j in range(i+1, min(i+10, len(lines))):
                        if 'Winter Energy per kWh' in lines[j]:
                            # Extract Charge Amount (first numeric value after the label)
                            rate_match = re.search(r'Winter Energy per kWh\s+(\d+\.\d+)', lines[j])
                            if rate_match:
                                rates["winter"] = float(rate_match.group(1))
                        elif 'Summer Energy per kWh' in lines[j]:
                            # Extract Charge Amount (first numeric value after the label)
                            rate_match = re.search(r'Summer Energy per kWh\s+(\d+\.\d+)', lines[j])
                            if rate_match:
                                rates["summer"] = float(rate_match.group(1))
            
            if rates:  # Found rates in summary format
                return rates
        
        # Original extraction logic for detailed tariff PDFs
        # Enhanced patterns for rate summaries which use more structured formats
        # Rate summary format: "Schedule R ... Energy Charge ... $0.XXXXX"
        summary_pattern = re.search(
            r"Schedule\s+R\b.*?Energy\s+Charge.*?\$(\d+\.\d+)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if summary_pattern:
            rate_value = float(summary_pattern.group(1))
            rates["standard"] = rate_value
            rates["summer"] = rate_value
            rates["winter"] = rate_value
            
        # Look for seasonal rates in summaries
        summer_match = re.search(
            r"Summer\s+(?:Period|Season)?.*?(?:Energy\s+Charge|per\s+kWh).*?\$(\d+\.\d+)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        winter_match = re.search(
            r"Winter\s+(?:Period|Season)?.*?(?:Energy\s+Charge|per\s+kWh).*?\$(\d+\.\d+)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        
        if summer_match:
            rates["summer"] = float(summer_match.group(1))
        if winter_match:
            rates["winter"] = float(winter_match.group(1))
        
        # Look for tiered rates (Schedule R pattern)
        tier1_match = re.search(
            r"First\s+(\d+)\s+(?:Kilowatt-Hours|kWh).*?(?:per\s+kWh|\$)\s*\.?\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier1_match:
            rate_value = float(tier1_match.group(2))
            if "summer" not in rates:
                rates["summer"] = rate_value
            if "winter" not in rates:
                rates["winter"] = rate_value
            rates["tier_1"] = rate_value
            
        # Look for additional tiers
        tier2_match = re.search(
            r"All additional.*?(?:Kilowatt-Hours|kWh).*?(?:per\s+kWh|\$)\s*\.?\s*(\d+\.?\d*)", 
            text, 
            re.IGNORECASE | re.DOTALL
        )
        if tier2_match:
            rates["tier_2"] = float(tier2_match.group(1))
        
        # Fallback to standard residential rate
        if not rates:
            standard_match = re.search(
                r"(?:Energy Charge|Standard).*?(?:per\s+(?:kWh|Kilowatt.hour)|\$)\s*\.?\s*(\d+\.?\d*)", 
                text, 
                re.IGNORECASE | re.DOTALL
            )
            if standard_match:
                rate_value = float(standard_match.group(1))
                rates["standard"] = rate_value
                rates["summer"] = rate_value
                rates["winter"] = rate_value
            
        return rates
    
    def _extract_tou_rates(self, text: str) -> Dict[str, Any]:
        """Extract time-of-use rates from Xcel Energy PDF text."""
        tou_rates = {"summer": {}, "winter": {}}
        
        # Check if this is a summary table format (April 2025 format)
        if "Total Monthly Rate" in text and "RE-TOU" in text:
            # This is a summary table - extract TOU rates from Charge Amount column
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'RE-TOU' in line or 'Residential Energy Time-Of-Use' in line:
                    # Look for TOU rates in following lines
                    for j in range(i+1, min(i+20, len(lines))):
                        line_text = lines[j]
                        
                        # Extract Charge Amount (first numeric value after the label)
                        # Winter rates
                        if 'Winter On-Peak Energy' in line_text or 'Winter Peak Energy' in line_text:
                            rate_match = re.search(r'Winter (?:On-Peak|Peak) Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["winter"]["peak"] = float(rate_match.group(1))
                        elif 'Winter Shoulder Energy' in line_text:
                            rate_match = re.search(r'Winter Shoulder Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["winter"]["shoulder"] = float(rate_match.group(1))
                        elif 'Winter Off-Peak Energy' in line_text:
                            rate_match = re.search(r'Winter Off-Peak Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["winter"]["off_peak"] = float(rate_match.group(1))
                        # Summer rates
                        elif 'Summer On-Peak Energy' in line_text or 'Summer Peak Energy' in line_text:
                            rate_match = re.search(r'Summer (?:On-Peak|Peak) Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["summer"]["peak"] = float(rate_match.group(1))
                        elif 'Summer Shoulder Energy' in line_text:
                            rate_match = re.search(r'Summer Shoulder Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["summer"]["shoulder"] = float(rate_match.group(1))
                        elif 'Summer Off-Peak Energy' in line_text:
                            rate_match = re.search(r'Summer Off-Peak Energy per kWh\s+(\d+\.\d+)', line_text)
                            if rate_match:
                                tou_rates["summer"]["off_peak"] = float(rate_match.group(1))
            
            if any(tou_rates["summer"].values()) or any(tou_rates["winter"].values()):
                return tou_rates
        
        # Original extraction logic for detailed tariff PDFs
        # Enhanced patterns for rate summaries which may use different formatting
        # Rate summaries often have "Schedule RE-TOU" or "Res TOU Service"
        tou_section_match = re.search(
            r"(?:Schedule\s+RE-?TOU|Res\s+TOU\s+Service|RESIDENTIAL.*?TIME.*?USE).*?(?=Schedule|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if tou_section_match:
            tou_text = tou_section_match.group(0)
            
            # Extract rates with enhanced patterns
            # Summer rates
            summer_patterns = {
                "peak": [
                    r"Summer.*?On-?Peak.*?\$(\d+\.\d+)",
                    r"Summer.*?Peak.*?\$(\d+\.\d+)",
                    r"Jun.*?Sep.*?On-?Peak.*?\$(\d+\.\d+)"
                ],
                "shoulder": [
                    r"Summer.*?Shoulder.*?\$(\d+\.\d+)",
                    r"Summer.*?Mid-?Peak.*?\$(\d+\.\d+)"
                ],
                "off_peak": [
                    r"Summer.*?Off-?Peak.*?\$(\d+\.\d+)",
                    r"Summer.*?Off\s+Peak.*?\$(\d+\.\d+)"
                ]
            }
            
            # Winter rates
            winter_patterns = {
                "peak": [
                    r"Winter.*?On-?Peak.*?\$(\d+\.\d+)",
                    r"Winter.*?Peak.*?\$(\d+\.\d+)",
                    r"Oct.*?May.*?On-?Peak.*?\$(\d+\.\d+)"
                ],
                "shoulder": [
                    r"Winter.*?Shoulder.*?\$(\d+\.\d+)",
                    r"Winter.*?Mid-?Peak.*?\$(\d+\.\d+)"
                ],
                "off_peak": [
                    r"Winter.*?Off-?Peak.*?\$(\d+\.\d+)",
                    r"Winter.*?Off\s+Peak.*?\$(\d+\.\d+)"
                ]
            }
            
            # Extract summer rates
            for period, patterns in summer_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, tou_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        tou_rates["summer"][period] = float(match.group(1))
                        break
            
            # Extract winter rates
            for period, patterns in winter_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, tou_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        tou_rates["winter"][period] = float(match.group(1))
                        break
        
        # Fallback to original extraction method if summary format not found
        if not any(tou_rates["summer"].values()) and not any(tou_rates["winter"].values()):
            # Xcel-specific TOU patterns
            patterns = {
                "peak": [
                    r"On-Peak.*?Period.*?\$(\d+\.?\d*)",
                    r"Peak.*?Period.*?\$(\d+\.?\d*)",
                    r"On.*Peak.*?\$(\d+\.?\d*)"
                ],
                "shoulder": [
                    r"Shoulder.*?Period.*?\$(\d+\.?\d*)",
                    r"Mid.*Peak.*?\$(\d+\.?\d*)"
                ],
                "off_peak": [
                    r"Off-Peak.*?Period.*?\$(\d+\.?\d*)",
                    r"Off.*Peak.*?\$(\d+\.?\d*)"
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
        
        # Check if this is a summary table format (April 2025 format)
        if "Total Monthly Rate" in text and "Residential ( R)" in text:
            # This is a summary table - extract from table format
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'Residential ( R)' in line or 'Residential (R)' in line:
                    # Look for service charge in following lines
                    for j in range(i+1, min(i+5, len(lines))):
                        if 'Service and Facility' in lines[j]:
                            # Extract Charge Amount (first numeric value after the label)
                            charge_match = re.search(r'Service and Facility per Month\s+(\d+\.\d+)', lines[j])
                            if charge_match:
                                charges["service_charge"] = float(charge_match.group(1))
                                charges["monthly_service"] = float(charge_match.group(1))  # Keep for compatibility
                                return charges
        
        # Original extraction logic for detailed tariff PDFs
        # Enhanced patterns for rate summaries
        patterns = {
            "monthly_service": [
                r"Service\s+(?:and\s+Facility\s+)?Charge.*?\$(\d+\.?\d*)",
                r"Basic\s+Service\s+Charge.*?\$(\d+\.?\d*)",
                r"Customer\s+Charge.*?\$(\d+\.?\d*)",
                r"Monthly\s+Service.*?\$(\d+\.?\d*)",
                # Rate summary specific patterns
                r"Service\s+&\s+Facility.*?\$(\d+\.?\d*)",
                r"Serv\s+&\s+Fac\s+Chg.*?\$(\d+\.?\d*)"
            ],
            "demand_charge": [
                r"Demand\s+Charge.*?\$(\d+\.?\d*)",
                r"(?:kW|Kilowatt)\s+Charge.*?\$(\d+\.?\d*)",
                r"Maximum\s+Demand.*?\$(\d+\.?\d*)"
            ]
        }
        
        for charge_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
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
        # First try to extract from summary title format "as of MM-DD-YY"
        summary_date_match = re.search(
            r"as\s+of\s+(\d{2})-(\d{2})-(\d{2})",
            text,
            re.IGNORECASE
        )
        if summary_date_match:
            month, day, year = summary_date_match.groups()
            # Convert to full date format
            year = f"20{year}"  # Convert 2-digit year to 4-digit
            # Convert to standard format
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            month_name = months[int(month) - 1]
            return f"{month_name} {int(day)}, {year}"
        
        # Fallback to standard patterns
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
        
        # Check if this is a rate summary page (highly relevant)
        if "summary of electric rates" in text_lower or "summary of gas rates" in text_lower:
            score += 50
        
        # Xcel-specific scoring
        if "xcel energy" in text_lower:
            score += 20
        
        if rate_schedule.lower() in text_lower:
            score += 30
        
        if "schedule" in text_lower and rate_schedule.replace("_", "").replace("-", "") in text_lower:
            score += 25
        
        # Look for rate-specific keywords
        rate_keywords = {
            "residential": ["residential", "schedule r", "res service"],
            "residential_tou": ["time of use", "tou", "schedule re", "res tou"],
            "commercial": ["commercial", "schedule c", "general service"]
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
        if "effective" in text_lower or "as of" in text_lower:
            score += 5
        
        # Boost score if we see rate tables or structured data
        if re.search(r"\$\d+\.\d+", text):  # Dollar amounts
            score += 10
        
        return score
    
    def _extract_season_section(self, text: str, season: str) -> str:
        """Extract text section for a specific season."""
        pattern = rf"{season}.*?(?=(?:Winter|Summer)|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(0) if match else ""
    
    async def _get_bundled_pdf(self, service_type: str) -> Tuple[Optional[Dict[str, Any]], Optional[bytes]]:
        """Get bundled PDF content and metadata.
        
        Automatically handles different source types based on prefix:
        - file:// - Load from bundled data folder
        - http:// or https:// - Download from URL
        
        Returns:
            Tuple of (metadata dict, pdf content bytes) or (None, None) if not found
        """
        try:
            # Get the path to the component directory
            current_file = Path(__file__)
            component_dir = current_file.parent.parent
            data_dir = component_dir / "data"
            
            # Read sources metadata
            metadata_file = component_dir / "sources.json"
            if not metadata_file.exists():
                _LOGGER.debug("No sources metadata file found")
                return None, None
            
            async with aiofiles.open(metadata_file, "r") as f:
                content = await f.read()
                metadata = json.loads(content)
            
            # Handle different metadata versions
            if "providers" in metadata:
                # Version 3.0 format
                pdf_entries = metadata.get("providers", {}).get("xcel_energy", {}).get(service_type, [])
            else:
                # Older format
                pdf_entries = metadata.get("pdfs", {}).get("xcel_energy", {}).get(service_type)
            
            if not pdf_entries:
                _LOGGER.debug("No bundled PDF info for %s service", service_type)
                return None, None
            
            # Handle list format (multiple PDFs)
            if isinstance(pdf_entries, list):
                # Try each entry in order (sorted by effective date, newest first)
                for entry in pdf_entries:
                    source = entry.get("source", "")
                    
                    # Determine how to get the PDF based on source prefix
                    if source.startswith("file://"):
                        # Load from bundled file
                        filename = source[7:]  # Remove file:// prefix
                        pdf_path = data_dir / filename
                        
                        if pdf_path.exists():
                            async with aiofiles.open(pdf_path, "rb") as f:
                                pdf_content = await f.read()
                            
                            # Create consistent info dict
                            pdf_info = {
                                "filename": filename,
                                "effective_date": entry.get("effective_date"),
                                "description": entry.get("description"),
                                "source": source
                            }
                            
                            _LOGGER.info("Loaded bundled PDF: %s (%d bytes) - Effective %s", 
                                       filename, len(pdf_content), 
                                       entry.get("effective_date", "unknown"))
                            return pdf_info, pdf_content
                        else:
                            _LOGGER.debug("Bundled PDF file not found: %s", pdf_path)
                    
                    elif source.startswith(("http://", "https://")):
                        # This would be handled by the main fetch_tariff_data method
                        # For bundled PDF loading, we skip URL sources
                        _LOGGER.debug("Skipping URL source in bundled PDF check: %s", source)
                        continue
                    
                    else:
                        _LOGGER.warning("Unknown source type: %s", source)
                
                _LOGGER.debug("No available bundled PDF files for %s service", service_type)
                return None, None
            
            else:
                # Old format - single PDF entry (backward compatibility)
                pdf_info = pdf_entries
                if not pdf_info.get("filename"):
                    _LOGGER.debug("No filename in bundled PDF info for %s service", service_type)
                    return None, None
                
                # Check if the PDF file exists
                pdf_path = data_dir / pdf_info["filename"]
                if not pdf_path.exists():
                    _LOGGER.warning("Bundled PDF file not found: %s", pdf_path)
                    return None, None
                
                # Read the PDF content
                async with aiofiles.open(pdf_path, "rb") as f:
                    pdf_content = await f.read()
                
                _LOGGER.info("Loaded bundled PDF: %s (%d bytes)", pdf_info["filename"], len(pdf_content))
                return pdf_info, pdf_content
            
        except Exception as e:
            _LOGGER.error("Error loading bundled PDF: %s", str(e))
            return None, None
    
    async def _get_url_sources(self, service_type: str) -> List[Dict[str, Any]]:
        """Get URL sources from metadata that need to be downloaded.
        
        Returns:
            List of entries with http:// or https:// sources, sorted by effective date
        """
        try:
            # Get the path to the component directory
            current_file = Path(__file__)
            component_dir = current_file.parent.parent
            
            # Read sources metadata
            metadata_file = component_dir / "sources.json"
            if not metadata_file.exists():
                return []
            
            async with aiofiles.open(metadata_file, "r") as f:
                content = await f.read()
                metadata = json.loads(content)
            
            # Handle different metadata versions
            if "providers" in metadata:
                # Version 3.0 format
                pdf_entries = metadata.get("providers", {}).get("xcel_energy", {}).get(service_type, [])
            else:
                # Older format - no URL sources in old format
                return []
            
            if not isinstance(pdf_entries, list):
                return []
            
            # Filter for URL sources only
            url_sources = []
            for entry in pdf_entries:
                source = entry.get("source", "")
                if source.startswith(("http://", "https://")):
                    url_sources.append(entry)
            
            return url_sources
            
        except Exception as e:
            _LOGGER.error("Error getting URL sources: %s", str(e))
            return []


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
    
    BASE_URL = "https://www.xcelenergy.com"
    STATIC_FILES_URL = "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/"
    RATE_BOOKS_URL = "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books"
    
    # Static PDF URLs for rate summaries - these are reliable and don't require authentication
    # Note: These URLs are updated periodically. The integration will try to fetch the latest
    # from the rate books page, but these serve as reliable fallbacks.
    RATE_SUMMARY_URLS = {
        "electric": [
            # Most recent first (as of 2024)
            f"{STATIC_FILES_URL}Electric_Summation_Sheet_All_Rates_05.01.2024.pdf",
            f"{STATIC_FILES_URL}Electric_Summation_Sheet_All_Rates_04.01.2024_FINAL.pdf",
            f"{STATIC_FILES_URL}Electric_Summation_Sheet_All Rates_1.1.2024.pdf",
            f"{STATIC_FILES_URL}Electric_Summation_Sheet_All_Rates_10.01.23_FINAL.pdf",
            f"{STATIC_FILES_URL}Electric_Summation_Sheet_All_Rates_07.01.23.pdf",
        ],
        "gas": [
            # Most recent first (as of 2024)
            f"{STATIC_FILES_URL}Summary_of_Gas_Rates_as_of-04-01-2024.pdf",
            f"{STATIC_FILES_URL}Summary_of_Gas_Rates_as_of-01-01-2024 (Correction).pdf",
            f"{STATIC_FILES_URL}Summary_of_Gas_Rates_as_of-10-01-2023.pdf",
            f"{STATIC_FILES_URL}Summary_of_Gas_Rates_as_of-07-01-2023.pdf",
        ]
    }
    
    # Fallback to full tariff PDFs if summaries fail
    FULL_TARIFF_URLS = {
        "CO": f"{STATIC_FILES_URL}PSCo_Electric_Entire_Tariff.pdf",  # Public Service Company of Colorado
        "MI": f"{STATIC_FILES_URL}MPCO_Electric_Entire_Tariff.pdf",  # Michigan 
        "MN": f"{STATIC_FILES_URL}NSP_MN_Electric_Entire_Tariff.pdf",  # Northern States Power - Minnesota
        "NM": f"{STATIC_FILES_URL}SPS_NM_Electric_Entire_Tariff.pdf",  # Southwestern Public Service - New Mexico
        "ND": f"{STATIC_FILES_URL}NSP_ND_Electric_Entire_Tariff.pdf",  # Northern States Power - North Dakota
        "SD": f"{STATIC_FILES_URL}NSP_SD_Electric_Entire_Tariff.pdf",  # Northern States Power - South Dakota
        "TX": f"{STATIC_FILES_URL}SPS_TX_Electric_Entire_Tariff.pdf",  # Southwestern Public Service - Texas
        "WI": f"{STATIC_FILES_URL}NSP_WI_Electric_Entire_Tariff.pdf",  # Northern States Power - Wisconsin
    }
    
    def get_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        """Get PDF URL configuration for Xcel Energy.
        
        Prioritizes sources.json URLs, then rate summary PDFs which are regularly updated and more focused.
        Falls back to full tariff PDFs if summaries are not available.
        """
        # First check sources.json for URL sources
        try:
            # Get the path to the component directory
            current_file = Path(__file__)
            component_dir = current_file.parent.parent
            
            # Read sources metadata
            metadata_file = component_dir / "sources.json"
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                
                # Get entries from sources.json
                if "providers" in metadata:
                    pdf_entries = metadata.get("providers", {}).get("xcel_energy", {}).get(service_type, [])
                    
                    if isinstance(pdf_entries, list) and pdf_entries:
                        # Look for URL sources
                        for entry in pdf_entries:
                            source = entry.get("source", "")
                            if source.startswith(("http://", "https://")):
                                _LOGGER.info("Using URL from sources.json: %s", source)
                                return {
                                    "url": source,
                                    "type": "pdf",
                                    "is_summary": True,
                                    "note": "Using URL from sources.json"
                                }
        except Exception as e:
            _LOGGER.warning("Error reading sources.json: %s", e)
        
        # Fall back to static rate summary from our static list
        summary_urls = self.RATE_SUMMARY_URLS.get(service_type, [])
        
        if summary_urls:
            # Use the most recent summary (first in list)
            url = summary_urls[0]
            return {
                "url": url,
                "type": "pdf",
                "is_summary": True,
                "note": "Using static rate summary PDF"
            }
        
        # Fallback to full tariff PDFs
        if service_type == "gas":
            # Gas URLs - replace Electric with Gas in the filename
            base_url = self.FULL_TARIFF_URLS.get(state, "")
            if base_url:
                url = base_url.replace("_Electric_", "_Gas_")
            else:
                url = ""
        else:
            url = self.FULL_TARIFF_URLS.get(state, "")
        
        return {
            "url": url,
            "type": "pdf",
            "is_summary": False,
            "note": "Using full tariff PDF (may be outdated)"
        }
    
    async def get_most_recent_summary_url(self, service_type: str) -> Optional[str]:
        """Fetch the rate books page and extract the most recent summary URL.
        
        This method dynamically finds the latest rate summary by parsing the rate books page.
        It looks for static PDF files which are more reliable than Salesforce links.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.RATE_BOOKS_URL) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Use regex to find static PDF links (more reliable than BeautifulSoup for this)
                        pattern = rf'href="([^"]*staticfiles[^"]*(?:Electric_Summation|Summary_of_{service_type.title()}_Rates)[^"]*\.pdf)"'
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        
                        if matches:
                            # Extract dates and sort to get most recent
                            dated_links = []
                            for href in matches:
                                # Extract date from filename
                                date_patterns = [
                                    r'(\d{2})[.-](\d{2})[.-](\d{4})',  # MM-DD-YYYY
                                    r'(\d{2})[.-](\d{2})[.-](\d{2})',   # MM-DD-YY
                                    r'(\d{1,2})[.-](\d{1,2})[.-](\d{4})',  # M-D-YYYY
                                ]
                                
                                for date_pattern in date_patterns:
                                    date_match = re.search(date_pattern, href)
                                    if date_match:
                                        groups = date_match.groups()
                                        if len(groups) == 3:
                                            month, day, year = groups
                                            # Convert 2-digit year to 4-digit
                                            if len(year) == 2:
                                                year = f"20{year}"
                                            try:
                                                date_obj = datetime(int(year), int(month), int(day))
                                                # Convert relative URL to absolute
                                                if href.startswith('/'):
                                                    full_url = f"{self.BASE_URL}{href}"
                                                else:
                                                    full_url = href
                                                dated_links.append((date_obj, full_url))
                                                break
                                            except ValueError:
                                                continue
                            
                            if dated_links:
                                # Sort by date descending and return most recent
                                dated_links.sort(key=lambda x: x[0], reverse=True)
                                most_recent_url = dated_links[0][1]
                                _LOGGER.info(f"Found most recent {service_type} rate summary: {most_recent_url}")
                                return most_recent_url
                            else:
                                _LOGGER.warning(f"Found {service_type} rate summaries but could not parse dates")
                        else:
                            _LOGGER.warning(f"No {service_type} rate summary PDFs found on rate books page")
                            
        except Exception as e:
            _LOGGER.warning("Failed to fetch rate books page: %s", str(e))
        
        return None
    
    async def get_dynamic_source_config(self, state: str, service_type: str, rate_schedule: str) -> Dict[str, Any]:
        """Try to get the most recent rate summary dynamically from the rate books page.
        
        This method attempts to fetch the latest rate summary URL by scraping the
        rate books page. If successful, it returns that URL. Otherwise, it falls
        back to the static configuration.
        """
        # Check if we have a bundled PDF first
        try:
            extractor = XcelEnergyPDFExtractor()
            bundled_info, _ = await extractor._get_bundled_pdf(service_type)
            if bundled_info:
                _LOGGER.info("Bundled PDF available for %s service", service_type)
        except Exception:
            pass
        
        # Try to get the most recent URL dynamically
        latest_url = await self.get_most_recent_summary_url(service_type)
        
        if latest_url:
            return {
                "url": latest_url,
                "type": "pdf",
                "is_summary": True,
                "note": "Using dynamically fetched rate summary PDF",
                "use_bundled_fallback": True  # Enable bundled fallback
            }
        
        # Fall back to static configuration
        config = self.get_source_config(state, service_type, rate_schedule)
        config["use_bundled_fallback"] = True  # Enable bundled fallback
        return config
    
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