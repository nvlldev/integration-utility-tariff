"""Simple test for PDF download without Home Assistant dependencies."""
import asyncio
import json
import aiohttp
from pathlib import Path
from io import BytesIO
import PyPDF2
import re


async def download_and_parse_pdf():
    """Download and parse PDF from sources.json URL."""
    # Load sources.json
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    sources_file = component_dir / "sources.json"
    
    with open(sources_file, 'r') as f:
        sources_data = json.load(f)
    
    # Get the URL
    xcel_sources = sources_data.get("providers", {}).get("xcel_energy", {}).get("electric", [])
    if not xcel_sources:
        print("No Xcel Energy electric sources found")
        return
    
    source_url = xcel_sources[0]["source"]
    print(f"Downloading from: {source_url}")
    print(f"Effective date: {xcel_sources[0]['effective_date']}")
    print(f"Description: {xcel_sources[0]['description']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url) as response:
                if response.status == 200:
                    pdf_content = await response.read()
                    print(f"\n✓ Downloaded {len(pdf_content):,} bytes")
                    
                    # Parse PDF
                    pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
                    print(f"✓ PDF has {len(pdf_reader.pages)} pages")
                    
                    # Extract text
                    all_text = ""
                    for page in pdf_reader.pages:
                        all_text += page.extract_text() + "\n"
                    
                    print(f"✓ Extracted {len(all_text)} total characters")
                    
                    # Look for rates
                    print("\n=== Searching for Rates ===")
                    
                    # Standard rates
                    winter_match = re.search(r'Winter Energy per kWh[^\$]*\$(\d+\.\d+)', all_text)
                    summer_match = re.search(r'Summer Energy per kWh[^\$]*\$(\d+\.\d+)', all_text)
                    
                    if winter_match:
                        print(f"✓ Found Winter rate: ${winter_match.group(1)}/kWh")
                    if summer_match:
                        print(f"✓ Found Summer rate: ${summer_match.group(1)}/kWh")
                    
                    # Service charge
                    service_match = re.search(r'Service & Facility[^\$]*\$(\d+\.\d+)', all_text)
                    if service_match:
                        print(f"✓ Found Service charge: ${service_match.group(1)}/month")
                    
                    # TOU rates
                    print("\n=== Time-of-Use Rates ===")
                    tou_patterns = [
                        (r'Winter Peak per kWh[^\$]*\$(\d+\.\d+)', 'Winter Peak'),
                        (r'Winter Shoulder per kWh[^\$]*\$(\d+\.\d+)', 'Winter Shoulder'),
                        (r'Winter Off-Peak per kWh[^\$]*\$(\d+\.\d+)', 'Winter Off-Peak'),
                        (r'Summer Peak per kWh[^\$]*\$(\d+\.\d+)', 'Summer Peak'),
                        (r'Summer Shoulder per kWh[^\$]*\$(\d+\.\d+)', 'Summer Shoulder'),
                        (r'Summer Off-Peak per kWh[^\$]*\$(\d+\.\d+)', 'Summer Off-Peak'),
                    ]
                    
                    for pattern, name in tou_patterns:
                        match = re.search(pattern, all_text)
                        if match:
                            print(f"✓ Found {name}: ${match.group(1)}/kWh")
                    
                    # Save first page preview
                    preview_lines = all_text.split('\n')[:20]
                    print("\n=== First Page Preview ===")
                    for line in preview_lines:
                        if line.strip():
                            print(f"  {line.strip()}")
                    
                    # Save PDF for inspection
                    test_pdf = Path(__file__).parent / "test_download.pdf"
                    with open(test_pdf, 'wb') as f:
                        f.write(pdf_content)
                    print(f"\n✓ Saved PDF to: {test_pdf}")
                    
                else:
                    print(f"\n✗ Download failed: HTTP {response.status}")
                    print(f"  Reason: {response.reason}")
                    
    except aiohttp.ClientError as e:
        print(f"\n✗ Network error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def test_pdf_structure():
    """Test the structure of the downloaded PDF."""
    test_pdf = Path(__file__).parent / "test_download.pdf"
    
    if not test_pdf.exists():
        print("No test PDF found. Run download test first.")
        return
    
    print("\n=== Analyzing PDF Structure ===")
    
    with open(test_pdf, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        
        print(f"Number of pages: {len(pdf_reader.pages)}")
        print(f"PDF metadata: {pdf_reader.metadata}")
        
        # Check if it's the summary format
        first_page = pdf_reader.pages[0].extract_text()
        
        if "Total Monthly Rate" in first_page:
            print("✓ This is a summary table format PDF")
        else:
            print("✓ This is a detailed tariff PDF")
        
        # Look for key sections
        key_terms = [
            "Residential",
            "Service & Facility",
            "Energy Charge",
            "Time of Use",
            "Peak",
            "Off-Peak",
            "kWh"
        ]
        
        print("\nKey terms found:")
        for term in key_terms:
            if term in first_page:
                print(f"  ✓ {term}")
            else:
                print(f"  ✗ {term}")


if __name__ == "__main__":
    print("=== Simple PDF Download Test ===\n")
    
    # Run tests
    asyncio.run(download_and_parse_pdf())
    asyncio.run(test_pdf_structure())
    
    print("\n✓ Test completed!")