#!/usr/bin/env python3
"""Test scraping actual PDF URLs from Xcel Energy rate books page."""

import requests
import re
from bs4 import BeautifulSoup

url = "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books"

print("Fetching Xcel Energy rate books page...")
response = requests.get(url, timeout=10)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links that mention rate summaries
    summary_links = []
    
    # Look for links with "Summary of Electric Rates" or "Summary of Gas Rates"
    for link in soup.find_all('a'):
        text = link.get_text(strip=True)
        href = link.get('href', '')
        
        if 'Summary of' in text and 'Rates' in text and href:
            # Extract date from text
            date_match = re.search(r'(\d{2}-\d{2}-\d{2})', text)
            date_str = date_match.group(1) if date_match else 'Unknown'
            
            summary_links.append({
                'text': text,
                'href': href,
                'date': date_str,
                'type': 'Electric' if 'Electric' in text else 'Gas'
            })
    
    print(f"\nFound {len(summary_links)} rate summary links:\n")
    
    # Group by type
    electric_links = [l for l in summary_links if l['type'] == 'Electric']
    gas_links = [l for l in summary_links if l['type'] == 'Gas']
    
    print("Electric Rate Summaries:")
    for link in electric_links[:5]:  # Show first 5
        print(f"  - {link['text']}")
        print(f"    Date: {link['date']}")
        print(f"    URL: {link['href']}")
        
        # Test if it's a direct PDF link
        if link['href'].startswith('http'):
            try:
                test_response = requests.get(link['href'], timeout=5, stream=True)
                content_type = test_response.headers.get('Content-Type', '')
                if 'pdf' in content_type.lower():
                    print("    ✓ Direct PDF link")
                else:
                    print(f"    ✗ Not a PDF ({content_type})")
                test_response.close()
            except:
                print("    ? Could not verify")
        print()
    
    print("\nGas Rate Summaries:")
    for link in gas_links[:3]:  # Show first 3
        print(f"  - {link['text']}")
        print(f"    Date: {link['date']}")
        print(f"    URL: {link['href']}")
        print()
    
    # Look for pattern in URLs
    print("\nAnalyzing URL patterns...")
    salesforce_pattern = r'salesforce\.com/sfc/p/([^/]+)/a/([^/]+)/([^/]+)'
    static_pattern = r'staticfiles/xe-responsive/(.+\.pdf)'
    
    sf_matches = 0
    static_matches = 0
    
    for link in summary_links:
        if re.search(salesforce_pattern, link['href']):
            sf_matches += 1
        elif re.search(static_pattern, link['href']):
            static_matches += 1
    
    print(f"  - Salesforce URLs: {sf_matches}")
    print(f"  - Static PDF URLs: {static_matches}")
    print(f"  - Other: {len(summary_links) - sf_matches - static_matches}")
    
else:
    print(f"Failed to fetch page: {response.status_code}")