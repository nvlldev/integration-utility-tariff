"""Unit tests for PDF extraction functionality."""
import pytest
from pathlib import Path
import sys
import os
from unittest.mock import Mock, patch
import json

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.utility_tariff.tariff_manager import GenericTariffManager


class TestPDFExtraction:
    """Test PDF extraction functionality."""
    
    @pytest.fixture
    def tariff_manager(self):
        """Create a tariff manager instance for testing."""
        # Mock HomeAssistant
        mock_hass = Mock()
        mock_hass.config.path.return_value = "/tmp/test"
        
        # Create tariff manager
        manager = GenericTariffManager(
            hass=mock_hass,
            state="CO",
            service_type="electric",
            rate_schedule="residential",
            options={}
        )
        
        # Set test PDF path
        test_pdf = Path(__file__).parent / "resources" / "test_co_electric.pdf"
        manager._pdf_cache_path = test_pdf
        
        return manager
    
    @pytest.fixture
    def tariff_manager_tou(self):
        """Create a TOU tariff manager instance for testing."""
        # Mock HomeAssistant
        mock_hass = Mock()
        mock_hass.config.path.return_value = "/tmp/test"
        
        # Create tariff manager
        manager = GenericTariffManager(
            hass=mock_hass,
            state="CO",
            service_type="electric",
            rate_schedule="residential_tou",
            options={}
        )
        
        # Set test PDF path
        test_pdf = Path(__file__).parent / "resources" / "test_co_electric.pdf"
        manager._pdf_cache_path = test_pdf
        
        return manager
    
    def test_extract_all_data_residential(self, tariff_manager):
        """Test extracting all data for residential rate schedule."""
        # Extract data
        extracted_data = tariff_manager._extract_all_data_from_pdf()
        
        # Print extracted data for debugging
        print("\n=== EXTRACTED DATA (Residential) ===")
        print(json.dumps(extracted_data, indent=2))
        
        # Test that we got all the expected data types
        assert "rates" in extracted_data
        assert "fixed_charges" in extracted_data
        assert "tou_rates" in extracted_data
        assert "additional_charges" in extracted_data
        
        # Test rates extraction
        rates = extracted_data["rates"]
        assert len(rates) > 0, "No rates were extracted"
        
        # For residential, we should have either seasonal or tiered rates
        assert any(key in rates for key in ["summer", "winter", "tier_1", "standard"]), \
            f"Expected seasonal or tiered rates, got: {rates}"
        
        # If we have tier_1, verify it's a reasonable value
        if "tier_1" in rates:
            assert 0.01 < rates["tier_1"] < 0.50, f"Tier 1 rate seems unreasonable: {rates['tier_1']}"
        
        # Test fixed charges extraction
        fixed_charges = extracted_data["fixed_charges"]
        assert len(fixed_charges) > 0, "No fixed charges were extracted"
        assert "monthly_service" in fixed_charges, "No monthly service charge found"
        assert 1.0 < fixed_charges["monthly_service"] < 50.0, \
            f"Monthly service charge seems unreasonable: {fixed_charges['monthly_service']}"
    
    def test_extract_all_data_tou(self, tariff_manager_tou):
        """Test extracting all data for TOU rate schedule."""
        # Extract data
        extracted_data = tariff_manager_tou._extract_all_data_from_pdf()
        
        # Print extracted data for debugging
        print("\n=== EXTRACTED DATA (TOU) ===")
        print(json.dumps(extracted_data, indent=2))
        
        # Test TOU rates extraction
        tou_rates = extracted_data["tou_rates"]
        assert len(tou_rates) > 0, "No TOU rates were extracted"
        
        # Check summer rates
        assert "summer" in tou_rates, "No summer TOU rates found"
        summer_rates = tou_rates["summer"]
        assert "peak" in summer_rates, "No summer peak rate found"
        assert "off_peak" in summer_rates, "No summer off-peak rate found"
        
        # Verify summer rates are reasonable
        assert 0.01 < summer_rates["peak"] < 0.50, f"Summer peak rate unreasonable: {summer_rates['peak']}"
        assert 0.01 < summer_rates["off_peak"] < 0.50, f"Summer off-peak rate unreasonable: {summer_rates['off_peak']}"
        assert summer_rates["peak"] > summer_rates["off_peak"], "Peak rate should be higher than off-peak"
        
        # Check winter rates
        assert "winter" in tou_rates, "No winter TOU rates found"
        winter_rates = tou_rates["winter"]
        assert "peak" in winter_rates, "No winter peak rate found"
        assert "off_peak" in winter_rates, "No winter off-peak rate found"
        
        # Verify winter rates are reasonable
        assert 0.01 < winter_rates["peak"] < 0.50, f"Winter peak rate unreasonable: {winter_rates['peak']}"
        assert 0.01 < winter_rates["off_peak"] < 0.50, f"Winter off-peak rate unreasonable: {winter_rates['off_peak']}"
        assert winter_rates["peak"] > winter_rates["off_peak"], "Peak rate should be higher than off-peak"
        
        # If shoulder rates exist, verify them
        if "shoulder" in summer_rates:
            assert summer_rates["peak"] > summer_rates["shoulder"] > summer_rates["off_peak"], \
                "Shoulder rate should be between peak and off-peak"
    
    def test_specific_rate_values(self, tariff_manager_tou):
        """Test that we extract the specific rate values we found in manual testing."""
        # Extract data
        extracted_data = tariff_manager_tou._extract_all_data_from_pdf()
        
        # Based on our manual testing, we know these values should be extracted
        expected_values = {
            "fixed_charges": {
                "monthly_service": 5.59
            },
            "tou_rates": {
                "summer": {
                    "peak": 0.13861,
                    "shoulder": 0.09497,
                    "off_peak": 0.05134
                },
                "winter": {
                    "peak": 0.08727,
                    "shoulder": 0.06930,
                    "off_peak": 0.05134
                }
            }
        }
        
        # Test fixed charges
        assert extracted_data["fixed_charges"]["monthly_service"] == expected_values["fixed_charges"]["monthly_service"], \
            f"Expected service charge ${expected_values['fixed_charges']['monthly_service']}, " \
            f"got ${extracted_data['fixed_charges'].get('monthly_service')}"
        
        # Test TOU rates
        for season in ["summer", "winter"]:
            for period in ["peak", "shoulder", "off_peak"]:
                expected = expected_values["tou_rates"][season][period]
                actual = extracted_data["tou_rates"].get(season, {}).get(period)
                assert actual == expected, \
                    f"Expected {season} {period} rate {expected}, got {actual}"
    
    def test_page_finding(self, tariff_manager, tariff_manager_tou):
        """Test that the page finding algorithm correctly identifies relevant pages."""
        import PyPDF2
        
        # Test for residential
        with open(tariff_manager._pdf_cache_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pages = tariff_manager._find_relevant_pages(pdf_reader)
            
            print(f"\nResidential relevant pages: {[p+1 for p in pages[:10]]}")
            
            # We should find some relevant pages
            assert len(pages) > 0, "No relevant pages found for residential"
            
            # Page 32 (index 31) should be highly ranked for Schedule R
            assert 31 in pages[:10], "Page 32 (Schedule R) not in top 10 pages"
        
        # Test for TOU
        with open(tariff_manager_tou._pdf_cache_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pages = tariff_manager_tou._find_relevant_pages(pdf_reader)
            
            print(f"TOU relevant pages: {[p+1 for p in pages[:10]]}")
            
            # We should find some relevant pages
            assert len(pages) > 0, "No relevant pages found for TOU"
            
            # Page 45 (index 44) should be highly ranked for RE-TOU
            assert 44 in pages[:10], "Page 45 (RE-TOU) not in top 10 pages"
    
    def test_extraction_methods_individually(self, tariff_manager_tou):
        """Test individual extraction methods."""
        import PyPDF2
        
        with open(tariff_manager_tou._pdf_cache_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Get page 45 which we know has RE-TOU rates
            page_text = pdf_reader.pages[44].extract_text()
            
            # Test fixed charges extraction
            fixed_charges = tariff_manager_tou._extract_fixed_charges(page_text)
            assert fixed_charges.get("monthly_service") == 5.59, \
                f"Expected service charge $5.59, got {fixed_charges.get('monthly_service')}"
            
            # Test TOU rates extraction
            tou_rates = tariff_manager_tou._extract_tou_rates(page_text)
            assert tou_rates["summer"]["peak"] == 0.13861, \
                f"Expected summer peak 0.13861, got {tou_rates['summer'].get('peak')}"
            assert tou_rates["winter"]["off_peak"] == 0.05134, \
                f"Expected winter off-peak 0.05134, got {tou_rates['winter'].get('off_peak')}"
    
    def test_rate_schedule_extraction(self, tariff_manager):
        """Test extraction of rate schedule name and metadata."""
        extracted_data = tariff_manager._extract_all_data_from_pdf()
        
        # We should extract some metadata
        assert extracted_data.get("rate_schedule_name") is not None or \
               extracted_data.get("effective_date") is not None or \
               extracted_data.get("season_definitions"), \
               "No metadata was extracted"
    
    def test_empty_pdf_handling(self, tariff_manager):
        """Test handling of empty or invalid PDF."""
        # Set path to non-existent file
        tariff_manager._pdf_cache_path = Path("/tmp/nonexistent.pdf")
        
        # Should not raise exception
        extracted_data = tariff_manager._extract_all_data_from_pdf()
        
        # Should return empty structure
        assert isinstance(extracted_data, dict)
        assert extracted_data["rates"] == {}
        assert extracted_data["tou_rates"] == {}


def run_tests():
    """Run tests without pytest for quick testing."""
    print("Running PDF extraction tests...\n")
    
    # Create test instances
    test = TestPDFExtraction()
    
    # Mock hass
    mock_hass = Mock()
    mock_hass.config.path.return_value = "/tmp/test"
    
    # Create managers
    manager_res = GenericTariffManager(
        hass=mock_hass,
        state="CO",
        service_type="electric",
        rate_schedule="residential",
        options={}
    )
    
    manager_tou = GenericTariffManager(
        hass=mock_hass,
        state="CO",
        service_type="electric",
        rate_schedule="residential_tou",
        options={}
    )
    
    # Set test PDF paths
    test_pdf = Path(__file__).parent / "resources" / "test_co_electric.pdf"
    manager_res._pdf_cache_path = test_pdf
    manager_tou._pdf_cache_path = test_pdf
    
    try:
        print("Test 1: Extract residential data...")
        test.test_extract_all_data_residential(manager_res)
        print("✓ Passed\n")
        
        print("Test 2: Extract TOU data...")
        test.test_extract_all_data_tou(manager_tou)
        print("✓ Passed\n")
        
        print("Test 3: Verify specific rate values...")
        test.test_specific_rate_values(manager_tou)
        print("✓ Passed\n")
        
        print("Test 4: Test page finding...")
        test.test_page_finding(manager_res, manager_tou)
        print("✓ Passed\n")
        
        print("Test 5: Test individual extraction methods...")
        test.test_extraction_methods_individually(manager_tou)
        print("✓ Passed\n")
        
        print("All tests passed! ✓")
        
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)