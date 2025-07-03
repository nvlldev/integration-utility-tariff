"""Test PDF parsing patterns with sample text."""

# Sample text that might appear in an Xcel Energy rate PDF
SAMPLE_PDF_TEXT = """
SCHEDULE R
RESIDENTIAL SERVICE

AVAILABILITY
Available to customers for residential purposes in single-family dwellings and 
individually-metered apartments.

MONTHLY RATE
Service and Facility Charge:  $13.13

Energy Charge:
Summer Billing Periods (June, July, August, September)
    All kWh per month: $0.07425 per kWh

Winter Billing Periods (All Other Months)
    All kWh per month: $0.05565 per kWh

SCHEDULE RE-TOU
RESIDENTIAL TIME-OF-USE SERVICE

Summer On-Peak Period: $0.14124 per kWh
Summer Shoulder Period: $0.09677 per kWh  
Summer Off-Peak Period: $0.05231 per kWh

Winter On-Peak Period: $0.08893 per kWh
Winter Shoulder Period: $0.07062 per kWh
Winter Off-Peak Period: $0.05231 per kWh

DEFINITION OF TIME PERIODS
On-Peak: 3:00 p.m. to 7:00 p.m., Monday through Friday
Shoulder: 1:00 p.m. to 3:00 p.m., Monday through Friday
Off-Peak: All other hours

Effective: April 1, 2025
"""


def test_rate_extraction():
    """Test extracting rates from sample text."""
    import re
    
    print("Testing Rate Extraction Patterns")
    print("=" * 60)
    
    # Test base rate extraction
    print("\n1. Testing Base Rate Extraction:")
    
    # Summer rate pattern
    summer_match = re.search(
        r"Summer.*?All\s+kWh.*?\$(\d+\.\d+)\s*per\s+kWh",
        SAMPLE_PDF_TEXT,
        re.IGNORECASE | re.DOTALL
    )
    if summer_match:
        print(f"   ✓ Summer rate: ${summer_match.group(1)}/kWh")
    
    # Winter rate pattern
    winter_match = re.search(
        r"Winter.*?All\s+kWh.*?\$(\d+\.\d+)\s*per\s+kWh",
        SAMPLE_PDF_TEXT,
        re.IGNORECASE | re.DOTALL
    )
    if winter_match:
        print(f"   ✓ Winter rate: ${winter_match.group(1)}/kWh")
    
    # Test TOU rate extraction
    print("\n2. Testing TOU Rate Extraction:")
    
    tou_patterns = [
        ("Summer On-Peak", r"Summer\s+On-Peak.*?\$(\d+\.\d+)"),
        ("Summer Shoulder", r"Summer\s+Shoulder.*?\$(\d+\.\d+)"),
        ("Summer Off-Peak", r"Summer\s+Off-Peak.*?\$(\d+\.\d+)"),
        ("Winter On-Peak", r"Winter\s+On-Peak.*?\$(\d+\.\d+)"),
        ("Winter Shoulder", r"Winter\s+Shoulder.*?\$(\d+\.\d+)"),
        ("Winter Off-Peak", r"Winter\s+Off-Peak.*?\$(\d+\.\d+)"),
    ]
    
    for name, pattern in tou_patterns:
        match = re.search(pattern, SAMPLE_PDF_TEXT, re.IGNORECASE)
        if match:
            print(f"   ✓ {name}: ${match.group(1)}/kWh")
    
    # Test fixed charge extraction
    print("\n3. Testing Fixed Charge Extraction:")
    
    service_charge_match = re.search(
        r"Service\s+and\s+Facility\s+Charge.*?\$(\d+\.\d+)",
        SAMPLE_PDF_TEXT,
        re.IGNORECASE
    )
    if service_charge_match:
        print(f"   ✓ Monthly Service Charge: ${service_charge_match.group(1)}")
    
    # Test TOU schedule extraction
    print("\n4. Testing TOU Schedule Extraction:")
    
    schedule_patterns = [
        ("On-Peak", r"On-Peak:\s*(.+?)(?:,|\n)"),
        ("Shoulder", r"Shoulder:\s*(.+?)(?:,|\n)"),
        ("Off-Peak", r"Off-Peak:\s*(.+?)(?:\n|$)"),
    ]
    
    for name, pattern in schedule_patterns:
        match = re.search(pattern, SAMPLE_PDF_TEXT, re.IGNORECASE)
        if match:
            print(f"   ✓ {name}: {match.group(1).strip()}")
    
    # Test effective date extraction
    print("\n5. Testing Effective Date Extraction:")
    
    date_match = re.search(
        r"Effective:\s*(\w+\s+\d{1,2},\s+\d{4})",
        SAMPLE_PDF_TEXT,
        re.IGNORECASE
    )
    if date_match:
        print(f"   ✓ Effective Date: {date_match.group(1)}")


def show_expected_output():
    """Show what the parsed data structure should look like."""
    print("\n\n" + "=" * 60)
    print("Expected Parsed Data Structure:")
    print("=" * 60)
    
    expected = {
        "rates": {
            "summer": 0.07425,
            "winter": 0.05565
        },
        "tou_rates": {
            "summer": {
                "peak": 0.14124,
                "shoulder": 0.09677,
                "off_peak": 0.05231
            },
            "winter": {
                "peak": 0.08893,
                "shoulder": 0.07062,
                "off_peak": 0.05231
            }
        },
        "fixed_charges": {
            "monthly_service": 13.13
        },
        "tou_schedule": {
            "peak": {"start": 15, "end": 19},      # 3 PM - 7 PM
            "shoulder": {"start": 13, "end": 15}   # 1 PM - 3 PM
        },
        "season_definitions": {
            "summer_months": "6,7,8,9"
        },
        "effective_date": "April 1, 2025",
        "data_source": "pdf",
        "pdf_source": "downloaded",
        "pdf_url": "https://storage.googleapis.com/cdn.pikaforge.com/..."
    }
    
    import json
    print(json.dumps(expected, indent=2))


if __name__ == "__main__":
    test_rate_extraction()
    show_expected_output()