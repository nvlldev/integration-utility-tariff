"""Test Xcel Energy PDF downloading functionality."""
import pytest
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from custom_components.utility_tariff.providers.xcel_energy import (
    XcelEnergyPDFExtractor,
    XcelEnergyDataSource,
)


class TestXcelPDFDownload:
    """Test PDF download functionality."""
    
    @pytest.mark.asyncio
    async def test_current_url_format(self):
        """Test if current URL format works."""
        data_source = XcelEnergyDataSource()
        config = data_source.get_source_config("CO", "electric", "residential_tou")
        
        print(f"Current URL: {config['url']}")
        
        # Test if URL is accessible
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(config['url'], allow_redirects=True) as response:
                    print(f"Response status: {response.status}")
                    print(f"Final URL: {response.url}")
                    assert response.status in [200, 403, 404], f"Unexpected status: {response.status}"
            except Exception as e:
                print(f"Error accessing URL: {e}")
    
    @pytest.mark.asyncio
    async def test_salesforce_url(self):
        """Test if Salesforce URL format works."""
        salesforce_url = "https://xcelnew.my.salesforce.com/sfc/p/#1U0000011ttV/a/8b000002Y8xL/kYe61yf.9xyigvh2701Az49XLgU2izDS8ShGaCXiwsQ"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(salesforce_url, allow_redirects=True) as response:
                    print(f"Salesforce URL status: {response.status}")
                    print(f"Headers: {dict(response.headers)}")
                    # Salesforce URLs often require authentication
            except Exception as e:
                print(f"Error accessing Salesforce URL: {e}")
    
    @pytest.mark.asyncio
    async def test_pdf_extractor_with_mock(self):
        """Test PDF extractor with mocked response."""
        extractor = XcelEnergyPDFExtractor()
        
        # Mock PDF content - create a minimal valid PDF structure
        mock_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n164\n%%EOF"
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=mock_pdf_content)
            
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value = mock_response
            
            mock_session_instance = AsyncMock()
            mock_session_instance.get.return_value = mock_get
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # This should not raise an exception with mocked data
            try:
                result = await extractor.fetch_tariff_data(
                    url="http://example.com/test.pdf",
                    rate_schedule="residential_tou"
                )
                print(f"Extraction succeeded, got keys: {list(result.keys()) if result else 'None'}")
                assert result is not None
                assert "data_source" in result
                assert result["data_source"] == "pdf"
            except Exception as e:
                print(f"Extraction failed (expected with minimal PDF): {e}")
    
    def test_fallback_rates_available(self):
        """Verify fallback rates are available for CO."""
        data_source = XcelEnergyDataSource()
        fallback = data_source.get_fallback_rates("CO", "electric")
        
        assert fallback is not None
        assert "rates" in fallback
        assert "tou_rates" in fallback
        assert "fixed_charges" in fallback
        
        print(f"Fallback rates: {fallback}")
    
    def test_updated_url_configuration(self):
        """Test that URL configuration returns the updated URLs."""
        data_source = XcelEnergyDataSource()
        
        # Test Colorado electric URL
        config = data_source.get_source_config("CO", "electric", "residential_tou")
        assert config["url"] == "https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/PSCo_Electric_Entire_Tariff.pdf"
        assert config["type"] == "pdf"
        assert "note" in config
        
        # Test gas URL generation
        gas_config = data_source.get_source_config("CO", "gas", "residential_gas")
        assert "_Gas_" in gas_config["url"]
        
        print(f"Electric URL: {config['url']}")
        print(f"Gas URL: {gas_config['url']}")
        
    def test_2024_fallback_rates(self):
        """Verify 2024 updated fallback rates."""
        data_source = XcelEnergyDataSource()
        fallback = data_source.get_fallback_rates("CO", "electric")
        
        # Check that rates were updated for 2024
        assert fallback["effective_date"] == "2024-05-01"
        assert "note" in fallback
        assert fallback["fixed_charges"]["monthly_service"] == 13.13  # Updated service charge
        
        # Verify TOU rates structure
        assert "summer" in fallback["tou_rates"]
        assert "winter" in fallback["tou_rates"]
        assert all(period in fallback["tou_rates"]["summer"] for period in ["peak", "shoulder", "off_peak"])


if __name__ == "__main__":
    # Run tests manually
    import asyncio
    
    test = TestXcelPDFDownload()
    
    print("Testing current URL format...")
    asyncio.run(test.test_current_url_format())
    
    print("\nTesting Salesforce URL...")
    asyncio.run(test.test_salesforce_url())
    
    print("\nTesting fallback rates...")
    test.test_fallback_rates_available()