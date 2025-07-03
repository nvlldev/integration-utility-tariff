#!/usr/bin/env python3
"""Test direct download of Xcel Energy rate PDFs."""

import requests
import ssl
import certifi

# Test URLs
urls_to_test = {
    "Electric Rate Summary 04-01-25": "https://xcelnew.my.salesforce.com/sfc/p/1U0000011ttV/a/R3000006iQ50/4ByHGcPYGKo9ZMSO8aM2fuPF2pzZvIqj8iaB8TxEIes",
    "Electric Rate Summary 01-01-25": "https://xcelnew.my.salesforce.com/sfc/p/1U0000011ttV/a/R3000001EpGg/bBFMfxJ0CSPDJZKXuqOa958cTpd.fykRFnV3Wa5PgLM",
    "Rate Books Page": "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books",
    "Old Format Tariff": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/PSCo_Electric_Entire_Tariff.pdf"
}

print("Testing Xcel Energy PDF URLs...\n")

for name, url in urls_to_test.items():
    print(f"Testing: {name}")
    print(f"URL: {url}")
    
    try:
        # Try with standard request
        response = requests.head(url, timeout=10, allow_redirects=True)
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
        
        # If it's a redirect, show final URL
        if response.history:
            print(f"  Redirected to: {response.url}")
            
        # Check if it's a PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            print("  ✓ This is a PDF file")
        elif 'html' in content_type:
            print("  ✗ This is an HTML page (not a direct PDF link)")
            
    except requests.exceptions.SSLError:
        print("  ✗ SSL Error - trying without verification...")
        try:
            response = requests.head(url, timeout=10, verify=False, allow_redirects=True)
            print(f"  Status (no SSL verify): {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
        except Exception as e:
            print(f"  ✗ Failed even without SSL verification: {str(e)}")
            
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
    
    print()

# Check if we can parse the rate books page to find direct PDF links
print("\nTrying to fetch and parse the rate books page...")
try:
    response = requests.get(urls_to_test["Rate Books Page"], timeout=10)
    if response.status_code == 200:
        # Look for PDF links in the content
        import re
        pdf_links = re.findall(r'href="([^"]+\.pdf[^"]*)"', response.text, re.IGNORECASE)
        print(f"Found {len(pdf_links)} PDF links on the page")
        
        # Also look for Salesforce links
        sf_links = re.findall(r'href="([^"]*salesforce[^"]+)"', response.text, re.IGNORECASE)
        print(f"Found {len(sf_links)} Salesforce links on the page")
        
        # Look for rate summary mentions
        rate_summaries = re.findall(r'Summary of (?:Electric|Gas) Rates[^<]+', response.text)
        print(f"\nFound {len(rate_summaries)} rate summary mentions:")
        for summary in rate_summaries[:5]:  # Show first 5
            print(f"  - {summary}")
            
except Exception as e:
    print(f"Failed to fetch rate books page: {str(e)}")