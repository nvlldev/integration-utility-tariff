"""Test parsing the new PDF format with proper column extraction."""
import sys
import os
from pathlib import Path
import PyPDF2
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_pdf_new_format(pdf_path):
    """Parse the new format PDF where rates are in the last column."""
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = pdf_reader.pages[0].extract_text()
        
    rates = {}
    tou_rates = {}
    fixed_charges = {}
    
    lines = text.split('\n')
    
    print("=== Parsing New PDF Format ===\n")
    
    # Find Residential (R) section
    for i, line in enumerate(lines):
        if 'Residential ( R)' in line:
            print(f"Found Residential section at line {i}")
            
            # Parse following lines
            for j in range(i+1, min(i+15, len(lines))):
                current_line = lines[j]
                
                # Service charge - look for the last number in the line
                if 'Service and Facility per Month' in current_line:
                    # Extract all numbers and take the last one
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        fixed_charges['service_charge'] = float(numbers[-1])
                        print(f"  Service charge: ${numbers[-1]}")
                
                # Winter energy rate
                elif 'Winter Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        rates['winter'] = float(numbers[-1])
                        print(f"  Winter rate: ${numbers[-1]}/kWh")
                
                # Summer energy rate
                elif 'Summer Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        rates['summer'] = float(numbers[-1])
                        print(f"  Summer rate: ${numbers[-1]}/kWh")
                
                # Stop at next section
                elif 'Residential Energy Time-Of-Use' in current_line:
                    break
    
    # Find TOU section
    for i, line in enumerate(lines):
        if 'Residential Energy Time-Of-Use' in line or '(RE-TOU)' in line:
            print(f"\nFound TOU section at line {i}")
            
            # Parse TOU rates
            for j in range(i+1, min(i+20, len(lines))):
                current_line = lines[j]
                
                # Winter TOU rates
                if 'Winter On-Peak Energy per kWh' in current_line or 'Winter Peak Energy per kWh' in current_line:
                    # Need to check next line too as value might wrap
                    combined = current_line + ' ' + (lines[j+1] if j+1 < len(lines) else '')
                    numbers = re.findall(r'(\d+\.\d+)', combined)
                    if numbers:
                        tou_rates['winter_peak'] = float(numbers[-1])
                        print(f"  Winter Peak: ${numbers[-1]}/kWh")
                
                elif 'Winter Shoulder Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        tou_rates['winter_shoulder'] = float(numbers[-1])
                        print(f"  Winter Shoulder: ${numbers[-1]}/kWh")
                
                elif 'Winter Off-Peak Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        tou_rates['winter_off_peak'] = float(numbers[-1])
                        print(f"  Winter Off-Peak: ${numbers[-1]}/kWh")
                
                # Summer TOU rates
                elif 'Summer On-Peak Energy per kWh' in current_line or 'Summer Peak Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        tou_rates['summer_peak'] = float(numbers[-1])
                        print(f"  Summer Peak: ${numbers[-1]}/kWh")
                
                elif 'Summer Shoulder Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        tou_rates['summer_shoulder'] = float(numbers[-1])
                        print(f"  Summer Shoulder: ${numbers[-1]}/kWh")
                
                elif 'Summer Off-Peak Energy per kWh' in current_line:
                    numbers = re.findall(r'(\d+\.\d+)', current_line)
                    if numbers:
                        tou_rates['summer_off_peak'] = float(numbers[-1])
                        print(f"  Summer Off-Peak: ${numbers[-1]}/kWh")
                
                # Stop at next section
                elif 'Residential General Opt-Out' in current_line or 'Small Commercial' in current_line:
                    break
    
    return {
        'rates': rates,
        'tou_rates': tou_rates,
        'fixed_charges': fixed_charges
    }


def validate_extracted_data(data):
    """Validate the extracted data."""
    print("\n=== Validation Results ===")
    
    valid = True
    
    # Check standard rates
    if data['rates']:
        print("\nStandard Rates:")
        if 'winter' in data['rates']:
            print(f"  ✓ Winter: ${data['rates']['winter']:.5f}/kWh")
        else:
            print("  ✗ Winter rate missing")
            valid = False
            
        if 'summer' in data['rates']:
            print(f"  ✓ Summer: ${data['rates']['summer']:.5f}/kWh")
        else:
            print("  ✗ Summer rate missing")
            valid = False
    else:
        print("\n✗ No standard rates found")
        valid = False
    
    # Check TOU rates
    if data['tou_rates']:
        print("\nTime-of-Use Rates:")
        expected_tou = ['winter_peak', 'winter_shoulder', 'winter_off_peak', 
                       'summer_peak', 'summer_shoulder', 'summer_off_peak']
        
        for period in expected_tou:
            if period in data['tou_rates']:
                print(f"  ✓ {period}: ${data['tou_rates'][period]:.5f}/kWh")
            else:
                print(f"  ✗ {period} missing")
                valid = False
    else:
        print("\n⚠ No TOU rates found (optional)")
    
    # Check fixed charges
    if data['fixed_charges']:
        print("\nFixed Charges:")
        if 'service_charge' in data['fixed_charges']:
            print(f"  ✓ Service charge: ${data['fixed_charges']['service_charge']:.2f}/month")
        else:
            print("  ✗ Service charge missing")
            valid = False
    else:
        print("\n✗ No fixed charges found")
        valid = False
    
    return valid


def generate_sensor_preview(data):
    """Show what Home Assistant sensors would be created."""
    print("\n=== Home Assistant Sensor Preview ===")
    
    print("\nEntity ID                                          | Value      | Unit")
    print("-" * 70)
    
    # Standard rates
    if 'winter' in data['rates']:
        print(f"sensor.xcel_energy_electric_winter_rate            | {data['rates']['winter']:.5f} | $/kWh")
    if 'summer' in data['rates']:
        print(f"sensor.xcel_energy_electric_summer_rate            | {data['rates']['summer']:.5f} | $/kWh")
    
    # Service charge
    if 'service_charge' in data['fixed_charges']:
        print(f"sensor.xcel_energy_electric_service_charge         | {data['fixed_charges']['service_charge']:.2f}    | $/month")
    
    # TOU rates
    for period, rate in sorted(data['tou_rates'].items()):
        sensor_name = f"sensor.xcel_energy_electric_{period}_rate"
        print(f"{sensor_name:<50} | {rate:.5f} | $/kWh")


if __name__ == "__main__":
    pdf_path = Path(__file__).parent / "test_download.pdf"
    
    if not pdf_path.exists():
        print("Error: test_download.pdf not found")
        exit(1)
    
    # Parse PDF
    data = parse_pdf_new_format(pdf_path)
    
    # Validate
    if validate_extracted_data(data):
        print("\n✓ PDF parsing successful!")
        generate_sensor_preview(data)
        print("\n✓ Integration test PASSED - PDF is compatible with sensor creation")
    else:
        print("\n✗ PDF parsing failed - check format")
        print("\n✗ Integration test FAILED")