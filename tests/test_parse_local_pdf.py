"""Test parsing the downloaded Xcel PDF."""
import PyPDF2
import re
from pathlib import Path


def parse_xcel_pdf(pdf_path):
    """Parse the Xcel Energy PDF."""
    print(f"Parsing PDF: {pdf_path}")
    print("=" * 60)
    
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        print(f"Total pages: {len(pdf_reader.pages)}")
        
        # Extract text from all pages
        all_text = ""
        for i, page in enumerate(pdf_reader.pages):
            try:
                text = page.extract_text()
                all_text += f"\n\n--- Page {i+1} ---\n{text}"
                
                # Look for key indicators
                if i < 5:  # Check first 5 pages
                    if "Schedule R" in text:
                        print(f"✓ Found Schedule R on page {i+1}")
                    if "Time of Use" in text or "TOU" in text:
                        print(f"✓ Found TOU rates on page {i+1}")
                    if "Service and Facility" in text or "Customer Charge" in text:
                        print(f"✓ Found fixed charges on page {i+1}")
                        
            except Exception as e:
                print(f"Error on page {i+1}: {e}")
        
        return all_text


def extract_rates(text):
    """Extract rates from PDF text."""
    print("\n\nExtracting Rates...")
    print("-" * 40)
    
    results = {
        "rates": {},
        "tou_rates": {"summer": {}, "winter": {}},
        "fixed_charges": {}
    }
    
    # Extract base rates
    # Look for patterns like "$0.07425 per kWh"
    rate_matches = re.finditer(r'\$(\d+\.\d+)\s*per\s*kWh', text, re.IGNORECASE)
    rates_found = []
    for match in rate_matches:
        rate = float(match.group(1))
        rates_found.append(rate)
        # Get context around the rate
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 50)
        context = text[start:end].replace('\n', ' ')
        print(f"Found rate ${rate:.5f}/kWh in context: ...{context}...")
    
    # Extract fixed charges
    charge_patterns = [
        (r'Service\s+and\s+Facility\s+Charge[:\s]*\$(\d+\.\d+)', 'monthly_service'),
        (r'Customer\s+Charge[:\s]*\$(\d+\.\d+)', 'monthly_service'),
        (r'Basic\s+Service\s+Charge[:\s]*\$(\d+\.\d+)', 'monthly_service'),
    ]
    
    for pattern, charge_type in charge_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            results["fixed_charges"][charge_type] = float(match.group(1))
            print(f"✓ Found {charge_type}: ${match.group(1)}")
    
    # Look for TOU rates specifically
    tou_patterns = {
        "summer": {
            "peak": r'Summer\s+On-?Peak[:\s]*\$(\d+\.\d+)',
            "shoulder": r'Summer\s+Shoulder[:\s]*\$(\d+\.\d+)',
            "off_peak": r'Summer\s+Off-?Peak[:\s]*\$(\d+\.\d+)',
        },
        "winter": {
            "peak": r'Winter\s+On-?Peak[:\s]*\$(\d+\.\d+)',
            "shoulder": r'Winter\s+Shoulder[:\s]*\$(\d+\.\d+)',
            "off_peak": r'Winter\s+Off-?Peak[:\s]*\$(\d+\.\d+)',
        }
    }
    
    for season, periods in tou_patterns.items():
        for period, pattern in periods.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                results["tou_rates"][season][period] = rate
                print(f"✓ Found {season} {period}: ${rate:.5f}/kWh")
    
    # Look for effective date
    date_match = re.search(r'Effective[:\s]+(\w+\s+\d{1,2},\s+\d{4})', text, re.IGNORECASE)
    if date_match:
        results["effective_date"] = date_match.group(1)
        print(f"✓ Effective date: {date_match.group(1)}")
    
    return results


def show_sample_text(text, pages=[0, 1]):
    """Show sample text from specific pages."""
    print("\n\nSample Text from PDF:")
    print("=" * 60)
    
    # Split by page markers
    page_splits = text.split("--- Page")
    
    for page_num in pages:
        if page_num < len(page_splits) - 1:
            page_text = page_splits[page_num + 1]
            # Get first 500 chars of the page
            sample = page_text[:500].strip()
            print(f"\nPage {page_num + 1} Sample:")
            print("-" * 40)
            print(sample)
            print("...")


if __name__ == "__main__":
    pdf_path = Path(__file__).parent / "xcel_test.pdf"
    
    if not pdf_path.exists():
        print(f"PDF not found at {pdf_path}")
        exit(1)
    
    # Parse PDF
    text = parse_xcel_pdf(pdf_path)
    
    # Extract rates
    results = extract_rates(text)
    
    # Show sample text
    show_sample_text(text)
    
    # Summary
    print("\n\nSummary of Extracted Data:")
    print("=" * 60)
    print(f"Total rates found: {len([r for s in results['tou_rates'].values() for r in s.values()]) + len(results['rates'])}")
    print(f"Fixed charges: {len(results['fixed_charges'])}")
    print(f"Has effective date: {'effective_date' in results}")