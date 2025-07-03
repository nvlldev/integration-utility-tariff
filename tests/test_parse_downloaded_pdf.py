"""Test parsing the downloaded PDF to verify sensor data extraction."""
import sys
import os
from pathlib import Path
from io import BytesIO
import PyPDF2
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_xcel_pdf(pdf_path):
    """Parse Xcel Energy PDF and extract rates."""
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        
        print(f"PDF has {len(pdf_reader.pages)} pages")
        
        # Extract all text
        all_text = ""
        for i, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            all_text += page_text + "\n"
            print(f"Page {i+1}: {len(page_text)} characters")
        
        return all_text


def extract_rates_from_text(text):
    """Extract rates using the same logic as the integration."""
    rates = {}
    tou_rates = {}
    fixed_charges = {}
    
    # Check if this is a summary table format
    if "Total Monthly Rate" in text and "Residential ( R)" in text:
        print("\n✓ Detected summary table format")
        
        # Split into lines for easier parsing
        lines = text.split('\n')
        
        # Find residential section
        for i, line in enumerate(lines):
            if 'Residential ( R)' in line or 'Residential (R)' in line:
                print(f"✓ Found Residential section at line {i}")
                
                # Look for rates in following lines
                for j in range(i+1, min(i+20, len(lines))):
                    current_line = lines[j]
                    
                    # Service charge
                    if 'Service & Facility' in current_line:
                        # Extract last number (total rate)
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            fixed_charges['service_charge'] = float(numbers[-1])
                            print(f"  Found service charge: ${numbers[-1]}")
                    
                    # Winter energy rate
                    elif 'Winter Energy per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            rates['winter'] = float(numbers[-1])
                            print(f"  Found winter rate: ${numbers[-1]}/kWh")
                    
                    # Summer energy rate
                    elif 'Summer Energy per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            rates['summer'] = float(numbers[-1])
                            print(f"  Found summer rate: ${numbers[-1]}/kWh")
                    
                    # TOU rates
                    elif 'Winter Peak per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['winter_peak'] = float(numbers[-1])
                            print(f"  Found winter peak: ${numbers[-1]}/kWh")
                    
                    elif 'Winter Shoulder per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['winter_shoulder'] = float(numbers[-1])
                            print(f"  Found winter shoulder: ${numbers[-1]}/kWh")
                    
                    elif 'Winter Off-Peak per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['winter_off_peak'] = float(numbers[-1])
                            print(f"  Found winter off-peak: ${numbers[-1]}/kWh")
                    
                    elif 'Summer Peak per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['summer_peak'] = float(numbers[-1])
                            print(f"  Found summer peak: ${numbers[-1]}/kWh")
                    
                    elif 'Summer Shoulder per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['summer_shoulder'] = float(numbers[-1])
                            print(f"  Found summer shoulder: ${numbers[-1]}/kWh")
                    
                    elif 'Summer Off-Peak per kWh' in current_line:
                        numbers = re.findall(r'\$(\d+\.\d+)', current_line)
                        if numbers:
                            tou_rates['summer_off_peak'] = float(numbers[-1])
                            print(f"  Found summer off-peak: ${numbers[-1]}/kWh")
    
    else:
        print("\n⚠ PDF format not recognized as summary table")
    
    return {
        'rates': rates,
        'tou_rates': tou_rates,
        'fixed_charges': fixed_charges
    }


def validate_sensor_data(data):
    """Validate the extracted sensor data."""
    print("\n=== Validating Sensor Data ===")
    
    # Check rates
    if data['rates']:
        print("\nStandard Rates:")
        for season, rate in data['rates'].items():
            status = "✓" if 0.05 <= rate <= 0.50 else "⚠"
            print(f"  {status} {season}: ${rate:.5f}/kWh")
        
        # Check if summer > winter
        if 'winter' in data['rates'] and 'summer' in data['rates']:
            if data['rates']['summer'] > data['rates']['winter']:
                print("  ✓ Summer rate is higher than winter (expected)")
            else:
                print("  ⚠ Summer rate is not higher than winter")
    
    # Check TOU rates
    if data['tou_rates']:
        print("\nTime-of-Use Rates:")
        for period, rate in sorted(data['tou_rates'].items()):
            status = "✓" if 0.05 <= rate <= 0.50 else "⚠"
            print(f"  {status} {period}: ${rate:.5f}/kWh")
        
        # Verify peak > off-peak
        peak_rates = [v for k, v in data['tou_rates'].items() if 'peak' in k and 'off' not in k]
        off_peak_rates = [v for k, v in data['tou_rates'].items() if 'off_peak' in k]
        
        if peak_rates and off_peak_rates:
            if min(peak_rates) > max(off_peak_rates):
                print("  ✓ All peak rates are higher than off-peak rates")
            else:
                print("  ⚠ Some peak rates may not be higher than off-peak")
    
    # Check fixed charges
    if data['fixed_charges']:
        print("\nFixed Charges:")
        for charge, amount in data['fixed_charges'].items():
            status = "✓" if 5 <= amount <= 20 else "⚠"
            print(f"  {status} {charge}: ${amount:.2f}/month")
    
    # Summary
    total_items = len(data['rates']) + len(data['tou_rates']) + len(data['fixed_charges'])
    print(f"\n✓ Extracted {total_items} total rate values")
    
    return total_items > 0


def test_integration_format():
    """Test that data matches the format expected by Home Assistant sensors."""
    pdf_path = Path(__file__).parent / "test_download.pdf"
    
    if not pdf_path.exists():
        print("Error: test_download.pdf not found")
        return False
    
    print("=== Testing Integration Format ===\n")
    
    # Parse PDF
    text = parse_xcel_pdf(pdf_path)
    
    # Extract rates
    data = extract_rates_from_text(text)
    
    # Validate
    if validate_sensor_data(data):
        print("\n✓ PDF parsing successful - data ready for sensors")
        
        # Show what sensors would be created
        print("\n=== Expected Home Assistant Sensors ===")
        
        if data['rates'].get('winter'):
            print(f"  sensor.xcel_energy_electric_winter_rate: {data['rates']['winter']} $/kWh")
        if data['rates'].get('summer'):
            print(f"  sensor.xcel_energy_electric_summer_rate: {data['rates']['summer']} $/kWh")
        
        if data['fixed_charges'].get('service_charge'):
            print(f"  sensor.xcel_energy_electric_service_charge: {data['fixed_charges']['service_charge']} $/month")
        
        if data['tou_rates']:
            print("\n  TOU Rate Sensors:")
            for period, rate in sorted(data['tou_rates'].items()):
                sensor_name = f"sensor.xcel_energy_electric_{period}_rate"
                print(f"    {sensor_name}: {rate} $/kWh")
        
        return True
    else:
        print("\n✗ No valid sensor data extracted")
        return False


if __name__ == "__main__":
    print("=== Testing PDF Parsing for Sensor Data ===\n")
    
    success = test_integration_format()
    
    if success:
        print("\n✓ Integration test PASSED - PDF can be used for sensor data")
    else:
        print("\n✗ Integration test FAILED")