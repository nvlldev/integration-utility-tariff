"""Test parsing the Xcel summary PDF format."""
import PyPDF2
import re
from pathlib import Path
import json


def parse_summary_pdf(pdf_path):
    """Parse the Xcel Energy summary PDF."""
    print(f"Parsing Summary PDF: {pdf_path}")
    print("=" * 60)
    
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        print(f"Total pages: {len(pdf_reader.pages)}")
        
        # This appears to be a single-page summary
        if len(pdf_reader.pages) > 0:
            text = pdf_reader.pages[0].extract_text()
            return text
    
    return ""


def extract_from_summary_table(text):
    """Extract rates from summary table format."""
    print("\nAnalyzing Summary Table Format...")
    print("-" * 60)
    
    # Show the full text to understand structure
    print("\nFull PDF Text:")
    print("=" * 60)
    print(text)
    print("=" * 60)
    
    results = {
        "rates": {},
        "tou_rates": {"summer": {}, "winter": {}},
        "fixed_charges": {},
        "effective_date": None
    }
    
    # Extract effective date
    date_match = re.search(r'Effective\s+(\w+\s+\d{1,2},\s+\d{4})', text, re.IGNORECASE)
    if date_match:
        results["effective_date"] = date_match.group(1)
        print(f"\n✓ Effective date: {date_match.group(1)}")
    
    # Look for specific rate schedules in table format
    # The PDF seems to have rates in a table with Schedule names and Total Monthly Rate
    
    # Try to find residential rates (Schedule R)
    residential_patterns = [
        r'(?:R|Residential)\s+[^\n]*?(\d+\.\d+)¢?\s*(?:per\s*kWh)?',
        r'Schedule\s+R[^\n]*?(\d+\.\d+)',
        r'Residential[^\n]*?(\d+\.\d+)¢',
    ]
    
    print("\nSearching for rate patterns...")
    
    # Look for any number followed by ¢ or "per kWh"
    rate_pattern = r'(\d+\.\d+)¢?\s*(?:per\s*kWh)?'
    rate_matches = list(re.finditer(rate_pattern, text))
    
    print(f"\nFound {len(rate_matches)} potential rate values:")
    for i, match in enumerate(rate_matches[:10]):  # Show first 10
        value = float(match.group(1))
        # Get context
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end].replace('\n', ' ')
        print(f"  {i+1}. {value} in context: ...{context}...")
    
    # Try to identify specific schedules
    lines = text.split('\n')
    print(f"\nAnalyzing {len(lines)} lines...")
    
    for i, line in enumerate(lines):
        # Look for schedule lines
        if re.search(r'Schedule\s+R(?:\s|$)', line, re.IGNORECASE):
            print(f"\nFound Schedule R on line {i+1}: {line}")
            # Look for rates in this line or nearby lines
            for j in range(max(0, i-2), min(len(lines), i+3)):
                if re.search(r'\d+\.\d+', lines[j]):
                    print(f"  Nearby line {j+1}: {lines[j]}")
    
    return results


def try_alternative_parsing(text):
    """Try alternative parsing approaches."""
    print("\n\nTrying Alternative Parsing...")
    print("-" * 60)
    
    # Split into sections by common delimiters
    sections = re.split(r'(?:Schedule|SCHEDULE)\s+', text)
    
    print(f"Found {len(sections)} sections")
    
    for i, section in enumerate(sections[:5]):  # First 5 sections
        if len(section.strip()) > 10:
            print(f"\nSection {i}:")
            print("-" * 40)
            # Show first 200 chars
            print(section[:200])
            print("...")
            
            # Look for rates in this section
            rates = re.findall(r'(\d+\.\d+)¢?\s*(?:per\s*kWh)?', section)
            if rates:
                print(f"Rates found: {rates}")


if __name__ == "__main__":
    pdf_path = Path(__file__).parent / "xcel_test.pdf"
    
    if not pdf_path.exists():
        print(f"PDF not found at {pdf_path}")
        exit(1)
    
    # Parse PDF
    text = parse_summary_pdf(pdf_path)
    
    # Extract from summary format
    results = extract_from_summary_table(text)
    
    # Try alternative parsing
    try_alternative_parsing(text)