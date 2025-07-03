"""Test parsing of Charge Amount column from PDF."""
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.providers.xcel_energy import XcelEnergyPDFExtractor
import PyPDF2


def test_charge_amount_extraction():
    """Test that we extract Charge Amount column instead of Total Monthly Rate."""
    
    # Load the test PDF
    pdf_path = Path(__file__).parent / "test_download.pdf"
    if not pdf_path.exists():
        print("Error: test_download.pdf not found")
        return
    
    # Extract text
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = pdf_reader.pages[0].extract_text()
    
    # Create extractor
    extractor = XcelEnergyPDFExtractor()
    
    print("=== Testing Charge Amount Extraction ===\n")
    
    # Test standard rates
    rates = extractor._extract_rates(text)
    print("Standard Rates:")
    print(f"  Winter: ${rates.get('winter', 0):.5f}/kWh (should be 0.08570)")
    print(f"  Summer: ${rates.get('summer', 0):.5f}/kWh (should be 0.10380)")
    
    # Test fixed charges
    charges = extractor._extract_fixed_charges(text)
    print(f"\nFixed Charges:")
    print(f"  Service Charge: ${charges.get('service_charge', 0):.2f}/month (should be 7.10)")
    
    # Test TOU rates
    tou_rates = extractor._extract_tou_rates(text)
    print(f"\nTOU Rates:")
    if 'winter' in tou_rates:
        print(f"  Winter Peak: ${tou_rates['winter'].get('peak', 0):.5f}/kWh (should be 0.13171)")
        print(f"  Winter Shoulder: ${tou_rates['winter'].get('shoulder', 0):.5f}/kWh (should be 0.10460)")
        print(f"  Winter Off-Peak: ${tou_rates['winter'].get('off_peak', 0):.5f}/kWh (should be 0.07749)")
    if 'summer' in tou_rates:
        print(f"  Summer Peak: ${tou_rates['summer'].get('peak', 0):.5f}/kWh (should be 0.20915)")
        print(f"  Summer Shoulder: ${tou_rates['summer'].get('shoulder', 0):.5f}/kWh (should be 0.14332)")
        print(f"  Summer Off-Peak: ${tou_rates['summer'].get('off_peak', 0):.5f}/kWh (should be 0.07749)")
    
    # Verify correctness
    print("\n=== Verification ===")
    correct_values = {
        'winter_rate': (rates.get('winter', 0), 0.08570),
        'summer_rate': (rates.get('summer', 0), 0.10380),
        'service_charge': (charges.get('service_charge', 0), 7.10),
        'winter_peak': (tou_rates.get('winter', {}).get('peak', 0), 0.13171),
        'summer_peak': (tou_rates.get('summer', {}).get('peak', 0), 0.20915),
    }
    
    all_correct = True
    for name, (actual, expected) in correct_values.items():
        if abs(actual - expected) < 0.0001:
            print(f"✓ {name}: Correct")
        else:
            print(f"✗ {name}: Expected {expected}, got {actual}")
            all_correct = False
    
    if all_correct:
        print("\n✅ All values extracted correctly from Charge Amount column!")
    else:
        print("\n❌ Some values are incorrect")
    
    return all_correct


if __name__ == "__main__":
    test_charge_amount_extraction()