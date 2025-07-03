#!/usr/bin/env python3
"""Find static PDF URLs from Xcel Energy rate books page."""

import requests
import re
from bs4 import BeautifulSoup

url = "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books"

print("Fetching Xcel Energy rate books page...")
response = requests.get(url, timeout=10)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links that point to staticfiles PDFs
    static_pdf_links = []
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        # Look for staticfiles PDF URLs
        if 'staticfiles' in href and href.endswith('.pdf'):
            # Extract date from text or filename
            date_match = re.search(r'(\d{2}[-.]?\d{2}[-.]?\d{2,4})', text) or re.search(r'(\d{2}[-.]?\d{2}[-.]?\d{2,4})', href)
            date_str = date_match.group(1) if date_match else 'Unknown'
            
            # Determine type
            if 'Electric' in text or 'Electric' in href:
                pdf_type = 'Electric'
            elif 'Gas' in text or 'Gas' in href:
                pdf_type = 'Gas'
            else:
                pdf_type = 'Unknown'
            
            # Check if it's a summary
            is_summary = 'Summ' in text or 'Summ' in href
            
            static_pdf_links.append({
                'text': text,
                'href': href,
                'date': date_str,
                'type': pdf_type,
                'is_summary': is_summary
            })
    
    print(f"\nFound {len(static_pdf_links)} static PDF links\n")
    
    # Filter for summaries
    summaries = [l for l in static_pdf_links if l['is_summary']]
    print(f"Found {len(summaries)} summary PDFs:\n")
    
    # Group by type
    electric_summaries = [l for l in summaries if l['type'] == 'Electric']
    gas_summaries = [l for l in summaries if l['type'] == 'Gas']
    
    print("Electric Rate Summary PDFs:")
    for link in electric_summaries[:10]:  # Show first 10
        print(f"  - {link['text']}")
        print(f"    Date: {link['date']}")
        print(f"    URL: {link['href']}")
        
        # Test if accessible
        if link['href'].startswith('http'):
            try:
                test_response = requests.head(link['href'], timeout=5)
                if test_response.status_code == 200:
                    print("    ✓ Accessible")
                else:
                    print(f"    ✗ Status: {test_response.status_code}")
            except:
                print("    ? Could not verify")
        print()
    
    print("\nGas Rate Summary PDFs:")
    for link in gas_summaries[:5]:  # Show first 5
        print(f"  - {link['text']}")
        print(f"    URL: {link['href']}")
        print()
    
    # Extract base URL pattern
    if electric_summaries:
        sample_url = electric_summaries[0]['href']
        base_match = re.search(r'(https://[^/]+/staticfiles/[^/]+/[^/]+/)', sample_url)
        if base_match:
            print(f"\nBase URL pattern: {base_match.group(1)}")
    
else:
    print(f"Failed to fetch page: {response.status_code}")