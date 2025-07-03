"""Simple test for Charge Amount extraction."""
import re
from pathlib import Path
import PyPDF2


def extract_rates(text):
    """Extract rates from Charge Amount column."""
    rates = {}
    
    if "Total Monthly Rate" in text and "Residential ( R)" in text:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Residential ( R)' in line:
                for j in range(i+1, min(i+10, len(lines))):
                    if 'Winter Energy per kWh' in lines[j]:
                        rate_match = re.search(r'Winter Energy per kWh\s+(\d+\.\d+)', lines[j])
                        if rate_match:
                            rates["winter"] = float(rate_match.group(1))
                    elif 'Summer Energy per kWh' in lines[j]:
                        rate_match = re.search(r'Summer Energy per kWh\s+(\d+\.\d+)', lines[j])
                        if rate_match:
                            rates["summer"] = float(rate_match.group(1))
    return rates


def extract_service_charge(text):
    """Extract service charge from Charge Amount column."""
    if "Total Monthly Rate" in text and "Residential ( R)" in text:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Residential ( R)' in line:
                for j in range(i+1, min(i+5, len(lines))):
                    if 'Service and Facility' in lines[j]:
                        charge_match = re.search(r'Service and Facility per Month\s+(\d+\.\d+)', lines[j])
                        if charge_match:
                            return float(charge_match.group(1))
    return None


def main():
    pdf_path = Path(__file__).parent / "test_download.pdf"
    if not pdf_path.exists():
        print("Error: test_download.pdf not found")
        return
    
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = pdf_reader.pages[0].extract_text()
    
    print("=== Testing Charge Amount Column Extraction ===\n")
    
    # Test rates
    rates = extract_rates(text)
    print(f"Winter rate: ${rates.get('winter', 0):.5f}/kWh (expected: 0.08570)")
    print(f"Summer rate: ${rates.get('summer', 0):.5f}/kWh (expected: 0.10380)")
    
    # Test service charge
    service_charge = extract_service_charge(text)
    if service_charge:
        print(f"Service charge: ${service_charge:.2f}/month (expected: 7.10)")
    
    # Check a few lines to debug
    print("\n=== Sample lines from PDF ===")
    lines = text.split('\n')
    for i, line in enumerate(lines[25:35]):
        print(f"{i+25}: {line}")


if __name__ == "__main__":
    main()