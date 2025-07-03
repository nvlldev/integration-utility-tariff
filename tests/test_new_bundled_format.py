"""Test the new bundled PDF format."""
import json
from pathlib import Path


def show_json_structure():
    """Show the new simplified JSON structure."""
    print("=== New Bundled PDF JSON Structure (v3.0) ===\n")
    
    example = {
        "version": "3.0",
        "providers": {
            "xcel_energy": {
                "electric": [
                    {
                        "source": "file://Electric_Rates_2024.pdf",
                        "effective_date": "2024-05-01",
                        "description": "Electric rates effective May 2024"
                    },
                    {
                        "source": "https://xcelenergy.com/rates_2025.pdf",
                        "effective_date": "2025-01-01", 
                        "description": "New rates for 2025"
                    }
                ],
                "gas": [
                    {
                        "source": "file://Gas_Rates_2024.pdf",
                        "effective_date": "2024-04-01",
                        "description": "Gas rates effective April 2024"
                    }
                ]
            }
        }
    }
    
    print(json.dumps(example, indent=2))
    
    print("\n\nKey Features:")
    print("1. Source prefix determines behavior:")
    print("   - file://    → Load from bundled data folder")
    print("   - http(s):// → Download from URL")
    print()
    print("2. Entries sorted by effective_date (newest first)")
    print("3. Integration automatically uses the latest available")
    print("4. No redundant fields - just source, date, and description")


def show_how_it_works():
    """Show how the integration uses the new format."""
    print("\n\n=== How It Works ===\n")
    
    print("1. When the integration starts:")
    print("   - Checks for file:// sources in order")
    print("   - Uses the first one that exists")
    print("   - Falls back to next if file missing")
    print()
    print("2. If no bundled files available:")
    print("   - Tries http(s):// sources")
    print("   - Downloads and uses the PDF")
    print()
    print("3. Data Source sensor shows:")
    print("   - 'Xcel Energy PDF' for downloaded")
    print("   - 'Xcel Energy PDF (Bundled)' for file://")
    print()
    print("4. To bundle PDFs for distribution:")
    print("   python scripts/bundle_pdf.py xcel_energy electric --download")
    print("   (This downloads http:// sources and converts to file://)")


def test_current_metadata():
    """Test the current metadata file."""
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    metadata_file = component_dir / "sources.json"
    
    print("\n\n=== Current Metadata ===\n")
    
    if not metadata_file.exists():
        print("No metadata file found")
        return
    
    with open(metadata_file, "r") as f:
        metadata = json.load(f)
    
    print(f"Version: {metadata.get('version')}")
    print(f"Providers: {list(metadata.get('providers', {}).keys())}")
    
    # Show Xcel Energy sources
    xcel = metadata.get('providers', {}).get('xcel_energy', {})
    for service_type, entries in xcel.items():
        print(f"\n{service_type.title()} sources:")
        for entry in entries:
            source = entry['source']
            prefix = source.split('://')[0] if '://' in source else 'unknown'
            print(f"  - {prefix}:// → {entry['effective_date']}")


if __name__ == "__main__":
    show_json_structure()
    show_how_it_works()
    test_current_metadata()