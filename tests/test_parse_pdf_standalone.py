"""Standalone test for PDF parsing without Home Assistant imports."""
import asyncio
import aiohttp
import PyPDF2
from io import BytesIO
import re


async def download_pdf(url: str) -> bytes:
    """Download PDF from URL."""
    print(f"Downloading PDF from: {url}")
    
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {response.reason}")
            
            content = await response.read()
            print(f"Downloaded {len(content):,} bytes")
            return content


def extract_rates_from_text(text: str) -> dict:
    """Extract rates from PDF text."""
    rates = {}
    
    # Look for rate patterns like "Schedule R ... $0.12345"
    rate_patterns = [
        # Schedule R pattern
        r"Schedule\s+R\b.*?Energy\s+Charge.*?\$(\d+\.\d+)",
        # Basic energy charge pattern
        r"Energy\s+Charge.*?\$(\d+\.\d+)",
        # Per kWh pattern
        r"per\s+(?:kWh|Kilowatt.hour).*?\$(\d+\.\d+)",
        # Rate with cents symbol
        r"(\d+\.\d+)¢\s*per\s*kWh",
    ]
    
    for pattern in rate_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for i, match in enumerate(matches):
            rate_value = float(match.group(1))
            # Convert cents to dollars if needed
            if "¢" in pattern:
                rate_value = rate_value / 100
            
            # Give meaningful names
            if i == 0:
                rates["standard"] = rate_value
            else:
                rates[f"tier_{i+1}"] = rate_value
    
    return rates


def extract_tou_rates_from_text(text: str) -> dict:
    """Extract TOU rates from PDF text."""
    tou_rates = {"summer": {}, "winter": {}}
    
    # Look for TOU patterns
    patterns = {
        "peak": [
            r"On-Peak.*?\$(\d+\.\d+)",
            r"Peak\s+Period.*?\$(\d+\.\d+)",
        ],
        "shoulder": [
            r"Shoulder.*?\$(\d+\.\d+)",
            r"Mid-Peak.*?\$(\d+\.\d+)",
        ],
        "off_peak": [
            r"Off-Peak.*?\$(\d+\.\d+)",
            r"Off\s+Peak.*?\$(\d+\.\d+)",
        ]
    }
    
    # Try to find summer/winter sections
    summer_match = re.search(r"Summer.*?(?=Winter|$)", text, re.IGNORECASE | re.DOTALL)
    winter_match = re.search(r"Winter.*?(?=Summer|$)", text, re.IGNORECASE | re.DOTALL)
    
    if summer_match:
        summer_text = summer_match.group(0)
        for period, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, summer_text, re.IGNORECASE)
                if match:
                    tou_rates["summer"][period] = float(match.group(1))
                    break
    
    if winter_match:
        winter_text = winter_match.group(0)
        for period, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, winter_text, re.IGNORECASE)
                if match:
                    tou_rates["winter"][period] = float(match.group(1))
                    break
    
    return tou_rates


def extract_fixed_charges_from_text(text: str) -> dict:
    """Extract fixed charges from PDF text."""
    charges = {}
    
    patterns = {
        "monthly_service": [
            r"Service\s+and\s+Facility\s+Charge.*?\$(\d+\.\d+)",
            r"Basic\s+Service\s+Charge.*?\$(\d+\.\d+)",
            r"Customer\s+Charge.*?\$(\d+\.\d+)",
            r"Monthly\s+Service\s+Charge.*?\$(\d+\.\d+)",
        ]
    }
    
    for charge_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                charges[charge_type] = float(match.group(1))
                break
    
    return charges


async def test_parse_pdf():
    """Test parsing the PDF."""
    url = "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf"
    
    print("Testing Xcel Energy PDF Parsing")
    print("=" * 60)
    
    try:
        # Download PDF
        pdf_content = await download_pdf(url)
        
        # Check if it's a PDF
        if not pdf_content.startswith(b'%PDF'):
            print("✗ Not a valid PDF file")
            return
        
        print("✓ Valid PDF file")
        
        # Parse PDF
        print("\nParsing PDF...")
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        print(f"Total pages: {len(pdf_reader.pages)}")
        
        # Extract text from first few pages
        combined_text = ""
        for i in range(min(10, len(pdf_reader.pages))):
            try:
                page_text = pdf_reader.pages[i].extract_text()
                combined_text += f"\n\n--- Page {i+1} ---\n{page_text}"
                
                # Look for rate schedule indicators
                if "Schedule R" in page_text:
                    print(f"Found Schedule R on page {i+1}")
                if "Time of Use" in page_text or "TOU" in page_text:
                    print(f"Found TOU rates on page {i+1}")
                    
            except Exception as e:
                print(f"Error extracting page {i+1}: {e}")
        
        # Extract rates
        print("\n" + "-" * 40)
        print("Extracting Rates...")
        
        rates = extract_rates_from_text(combined_text)
        if rates:
            print("\nBase Rates Found:")
            for rate_type, value in rates.items():
                print(f"  {rate_type}: ${value:.5f}/kWh")
        else:
            print("No base rates found")
        
        # Extract TOU rates
        tou_rates = extract_tou_rates_from_text(combined_text)
        if any(tou_rates.values()):
            print("\nTOU Rates Found:")
            for season, season_rates in tou_rates.items():
                if season_rates:
                    print(f"  {season.title()}:")
                    for period, rate in season_rates.items():
                        print(f"    {period}: ${rate:.5f}/kWh")
        else:
            print("No TOU rates found")
        
        # Extract fixed charges
        charges = extract_fixed_charges_from_text(combined_text)
        if charges:
            print("\nFixed Charges Found:")
            for charge_type, value in charges.items():
                print(f"  {charge_type}: ${value:.2f}")
        else:
            print("No fixed charges found")
        
        # Show sample text to debug
        print("\n" + "-" * 40)
        print("Sample PDF Text (first 1000 chars):")
        print(combined_text[:1000])
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_parse_pdf())