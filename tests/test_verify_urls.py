#!/usr/bin/env python3
"""Verify that the new static PDF URLs work correctly."""

import requests

# Test the static rate summary URLs
urls_to_test = {
    "Electric Summary 05-01-2024": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Electric_Summation_Sheet_All_Rates_05.01.2024.pdf",
    "Electric Summary 04-01-2024": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Electric_Summation_Sheet_All_Rates_04.01.2024_FINAL.pdf",
    "Gas Summary 04-01-2024": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Summary_of_Gas_Rates_as_of-04-01-2024.pdf",
    "Full Tariff CO": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/PSCo_Electric_Entire_Tariff.pdf"
}

print("Testing Xcel Energy static PDF URLs...\n")

for name, url in urls_to_test.items():
    print(f"Testing: {name}")
    print(f"URL: {url}")
    
    try:
        # Test with HEAD request first
        response = requests.head(url, timeout=10, allow_redirects=True)
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
        
        if response.status_code == 200:
            # Verify it's a PDF
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' in content_type:
                print("  ✓ Valid PDF URL")
                
                # Try to download first 1KB to verify it's readable
                try:
                    partial_response = requests.get(url, headers={'Range': 'bytes=0-1024'}, timeout=5)
                    if partial_response.content.startswith(b'%PDF'):
                        print("  ✓ Confirmed PDF content")
                    else:
                        print("  ? Content doesn't start with PDF header")
                except:
                    pass
            else:
                print("  ✗ Not a PDF")
        else:
            print("  ✗ Failed to access")
            
    except requests.exceptions.SSLError:
        print("  ✗ SSL Error")
        # Try without SSL verification
        try:
            response = requests.head(url, timeout=10, verify=False, allow_redirects=True)
            print(f"  Status (no SSL verify): {response.status_code}")
            if response.status_code == 200:
                print("  Note: URL works but has SSL issues in test environment")
        except Exception as e:
            print(f"  ✗ Failed even without SSL verification: {str(e)}")
            
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
    
    print()