"""Test downloading the Salesforce PDF and analyzing the response."""
import asyncio
import aiohttp
import ssl

async def download_salesforce_pdf():
    """Try to download the Salesforce PDF and analyze what we get."""
    
    pdf_url = "https://xcelnew.my.salesforce.com/sfc/p/1U0000011ttV/a/8b000002Y8xL/kYe61yf.9xyigvh2701Az49XLgU2izDS8ShGaCXiwsQ"
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Try with browser-like headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.xcelenergy.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        try:
            print("Attempting to download PDF...")
            async with session.get(pdf_url, headers=headers, allow_redirects=True) as response:
                print(f"Status: {response.status}")
                print(f"Final URL: {response.url}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                print(f"Content-Length: {response.headers.get('Content-Length', 'Not specified')}")
                
                # Check cookies - might need authentication
                print(f"\nCookies received: {len(response.cookies)}")
                for key in response.cookies.keys():
                    print(f"  - {key}")
                
                # Read first part of response to check what we got
                content = await response.read()
                print(f"\nContent size: {len(content)} bytes")
                
                # Check if it's a PDF
                if content.startswith(b'%PDF'):
                    print("✓ This is a valid PDF file!")
                    # Save it for testing
                    with open('/tmp/xcel_rate_book.pdf', 'wb') as f:
                        f.write(content)
                    print("Saved to /tmp/xcel_rate_book.pdf")
                    return True
                else:
                    # It's probably HTML
                    print("✗ Not a PDF file")
                    html_preview = content[:1000].decode('utf-8', errors='ignore')
                    
                    # Check for common patterns
                    if 'login' in html_preview.lower():
                        print("→ Appears to be a login page")
                    elif 'session' in html_preview.lower():
                        print("→ Mentions session (might need authentication)")
                    elif 'error' in html_preview.lower():
                        print("→ Contains error message")
                    
                    # Save HTML for inspection
                    with open('/tmp/xcel_response.html', 'w') as f:
                        f.write(content.decode('utf-8', errors='ignore'))
                    print("\nSaved HTML response to /tmp/xcel_response.html")
                    
                    # Look for any JavaScript redirects or authentication requirements
                    if 'window.location' in html_preview:
                        print("→ Contains JavaScript redirect")
                    if 'authentication' in html_preview.lower() or 'authorize' in html_preview.lower():
                        print("→ Requires authentication")
                        
        except Exception as e:
            print(f"Error: {e}")
            return False


async def test_direct_pdf_urls():
    """Test the older direct PDF URLs that don't require authentication."""
    
    urls_to_test = [
        {
            "name": "PSCo Electric Tariff (Public)",
            "url": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/PSCo_Electric_Entire_Tariff.pdf"
        },
        {
            "name": "April 2024 Summary",
            "url": "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Electric_Summation_Sheet_All_Rates_04.01.2024_FINAL.pdf"
        }
    ]
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        for pdf_info in urls_to_test:
            print(f"\n\nTesting: {pdf_info['name']}")
            print(f"URL: {pdf_info['url']}")
            
            try:
                async with session.head(pdf_info['url']) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        print(f"✓ Accessible without authentication")
                        print(f"Size: {response.headers.get('Content-Length', 'Unknown')} bytes")
                        print(f"Last-Modified: {response.headers.get('Last-Modified', 'Unknown')}")
                    else:
                        print(f"✗ Not accessible (Status: {response.status})")
            except Exception as e:
                print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("=== Testing Salesforce PDF Download ===")
    asyncio.run(download_salesforce_pdf())
    
    print("\n\n=== Testing Public PDF URLs ===")
    asyncio.run(test_direct_pdf_urls())