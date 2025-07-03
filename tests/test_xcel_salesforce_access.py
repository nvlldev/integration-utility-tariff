"""Test accessing Xcel Energy rate books through their website."""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json

async def find_rate_book_links():
    """Navigate Xcel Energy website to find rate book links."""
    
    # Start at the rate books page
    rate_books_url = "https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books"
    
    # Create SSL context that doesn't verify certificates (for testing only)
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Get the rate books page
            async with session.get(rate_books_url) as response:
                print(f"Rate books page status: {response.status}")
                if response.status != 200:
                    print(f"Failed to access rate books page: {response.status}")
                    return
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for links containing "electric" or "rate book"
                links = soup.find_all('a', href=True)
                electric_links = []
                
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True).lower()
                    
                    if 'electric' in text or 'electric' in href:
                        electric_links.append({
                            'text': link.get_text(strip=True),
                            'href': href,
                            'full_url': href if href.startswith('http') else f"https://www.xcelenergy.com{href}"
                        })
                
                print(f"\nFound {len(electric_links)} electric-related links:")
                for idx, link in enumerate(electric_links[:10]):  # Show first 10
                    print(f"{idx+1}. {link['text']}")
                    print(f"   URL: {link['href']}")
                
                # Look for Salesforce links
                salesforce_links = [link for link in links if 'salesforce.com' in link.get('href', '')]
                if salesforce_links:
                    print(f"\nFound {len(salesforce_links)} Salesforce links:")
                    for link in salesforce_links[:5]:
                        print(f"- {link.get_text(strip=True)}")
                        print(f"  URL: {link.get('href')}")
                
                # Look for JavaScript onclick handlers that might open PDFs
                onclick_elements = soup.find_all(attrs={'onclick': True})
                if onclick_elements:
                    print(f"\nFound {len(onclick_elements)} elements with onclick handlers")
                    for elem in onclick_elements[:5]:
                        onclick = elem.get('onclick', '')
                        if 'pdf' in onclick.lower() or 'salesforce' in onclick.lower():
                            print(f"- {elem.get_text(strip=True)}")
                            print(f"  onclick: {onclick}")
                
                # Look for data attributes that might contain URLs
                data_elements = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
                pdf_data_elements = []
                for elem in data_elements:
                    for key, value in elem.attrs.items():
                        if key.startswith('data-') and value and ('.pdf' in str(value) or 'salesforce' in str(value)):
                            pdf_data_elements.append({
                                'text': elem.get_text(strip=True),
                                'attr': key,
                                'value': value
                            })
                
                if pdf_data_elements:
                    print(f"\nFound {len(pdf_data_elements)} elements with PDF/Salesforce data attributes:")
                    for elem in pdf_data_elements[:5]:
                        print(f"- {elem['text']}")
                        print(f"  {elem['attr']}: {elem['value']}")
                
                # Try to find specific rate book sections
                rate_book_sections = soup.find_all(['div', 'section'], class_=re.compile('rate.*book|book.*rate', re.I))
                if rate_book_sections:
                    print(f"\nFound {len(rate_book_sections)} rate book sections")
                    for section in rate_book_sections[:3]:
                        print(f"- Section: {section.get('class')}")
                        links_in_section = section.find_all('a', href=True)
                        for link in links_in_section[:3]:
                            print(f"  - {link.get_text(strip=True)}: {link.get('href')}")
                
        except Exception as e:
            print(f"Error accessing rate books page: {e}")


async def test_salesforce_pdf_access():
    """Test accessing the Salesforce PDF directly."""
    salesforce_url = "https://xcelnew.my.salesforce.com/sfc/p/#1U0000011ttV/a/8b000002Y8xL/kYe61yf.9xyigvh2701Az49XLgU2izDS8ShGaCXiwsQ"
    
    # Create SSL context that doesn't verify certificates (for testing only)
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Try different approaches to access the PDF
            
            # 1. Direct GET request
            print("\n1. Trying direct GET request...")
            async with session.get(salesforce_url, allow_redirects=True) as response:
                print(f"   Status: {response.status}")
                print(f"   Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
                print(f"   Content-Length: {response.headers.get('Content-Length', 'Not specified')}")
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'pdf' in content_type:
                        print("   ✓ Successfully accessed PDF!")
                        return True
                    else:
                        # Check if it's HTML (might be a login page)
                        if 'html' in content_type:
                            html = await response.text()
                            if 'login' in html.lower() or 'sign in' in html.lower():
                                print("   ✗ Redirected to login page")
                            else:
                                print("   ? Got HTML response (not PDF)")
            
            # 2. Try with different headers
            print("\n2. Trying with browser headers...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,*/*',
                'Referer': 'https://www.xcelenergy.com/'
            }
            async with session.get(salesforce_url, headers=headers, allow_redirects=True) as response:
                print(f"   Status: {response.status}")
                print(f"   Final URL: {response.url}")
                
        except Exception as e:
            print(f"Error accessing Salesforce PDF: {e}")
            return False


if __name__ == "__main__":
    print("=== Searching for Xcel Energy Rate Book Links ===")
    asyncio.run(find_rate_book_links())
    
    print("\n\n=== Testing Salesforce PDF Access ===")
    asyncio.run(test_salesforce_pdf_access())