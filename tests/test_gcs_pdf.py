"""Test downloading PDF from Google Cloud Storage."""
import asyncio
import aiohttp


async def test_gcs_pdf():
    """Test the Google Cloud Storage PDF URL."""
    url = "https://storage.googleapis.com/cdn.pikaforge.com/hass/utility-tariff/xcel-energy/electric/all-rates-04-01-2025.pdf"
    
    print("Testing Google Cloud Storage PDF URL...")
    print(f"URL: {url}\n")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as response:
                print(f"Status: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                print(f"Content-Length: {response.headers.get('Content-Length', 'Unknown')} bytes")
                
                if response.status == 200:
                    print("\n✓ PDF is accessible!")
                    
                    # Try downloading a small portion
                    async with session.get(url, headers={'Range': 'bytes=0-1023'}) as partial:
                        content = await partial.read()
                        if content.startswith(b'%PDF'):
                            print("✓ Confirmed PDF format")
                        else:
                            print("✗ Not a PDF file")
                else:
                    print(f"\n✗ Unable to access PDF (Status: {response.status})")
                    
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_gcs_pdf())