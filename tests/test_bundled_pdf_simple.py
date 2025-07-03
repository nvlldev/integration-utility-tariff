"""Simple test for tariff sources functionality without Home Assistant imports."""
import json
from pathlib import Path


def test_metadata_format():
    """Test the tariff sources metadata format."""
    # Get the path to the component directory
    current_file = Path(__file__)
    component_dir = current_file.parent.parent / "custom_components" / "utility_tariff"
    data_dir = component_dir / "data"
    metadata_file = component_dir / "sources.json"
    
    print("=== Testing Tariff Sources Metadata ===\n")
    
    if not metadata_file.exists():
        print("✗ No metadata file found at:", metadata_file)
        return
    
    with open(metadata_file, "r") as f:
        metadata = json.load(f)
    
    print(f"Metadata version: {metadata.get('version', '1.0')}")
    
    # Handle both old and new format
    if "providers" in metadata:
        # New format
        providers = metadata.get("providers", {})
        print(f"Found {len(providers)} providers\n")
        xcel_pdfs = providers.get("xcel_energy", {})
    else:
        # Old format
        print(f"Found {len(metadata.get('pdfs', {}))} providers\n")
        xcel_pdfs = metadata.get("pdfs", {}).get("xcel_energy", {})
    if not xcel_pdfs:
        print("✗ No Xcel Energy entries found")
        return
    
    for service_type, entries in xcel_pdfs.items():
        print(f"{service_type.upper()} Service:")
        print("-" * 40)
        
        if isinstance(entries, list):
            print(f"Format: New (supports multiple sources)")
            print(f"Total entries: {len(entries)}")
            
            # Show all entries
            for i, entry in enumerate(entries):
                print(f"\nEntry {i+1}:")
                print(f"  Source: {entry.get('source', 'unknown')}")
                print(f"  Type: {entry.get('source_type', 'unknown')}")
                print(f"  Filename: {entry.get('filename', 'unknown')}")
                print(f"  Version: {entry.get('version', 'unknown')}")
                print(f"  Effective: {entry.get('effective_date', 'unknown')}")
                print(f"  Description: {entry.get('description', 'unknown')}")
                
                # Check if file exists
                pdf_path = data_dir / entry.get('filename', '')
                if pdf_path.exists():
                    print(f"  File exists: ✓ ({pdf_path.stat().st_size:,} bytes)")
                else:
                    print(f"  File exists: ✗")
        else:
            # Old format
            print(f"Format: Old (single source)")
            print(f"  Filename: {entries.get('filename', 'unknown')}")
            print(f"  Version: {entries.get('version', 'unknown')}")
            print(f"  Effective: {entries.get('effective_date', 'unknown')}")
        
        print()


def test_bundle_script():
    """Show how to use the manage sources script."""
    print("\n=== How to Manage Tariff Sources ===\n")
    
    print("To manage tariff sources, use the manage_sources.py script:")
    print()
    print("1. Add source from URL:")
    print('   python scripts/manage_sources.py xcel_energy electric \\')
    print('     --source "https://www.xcelenergy.com/.../Electric_Rates.pdf"')
    print()
    print("2. Add source from local file:")
    print('   python scripts/manage_sources.py xcel_energy gas \\')
    print('     --source "/path/to/downloaded/Gas_Rates.pdf"')
    print()
    print("3. Add source with custom date:")
    print('   python scripts/manage_sources.py xcel_energy electric \\')
    print('     --source "file:///path/to/rates.pdf" \\')
    print('     --effective-date 2025-01-01')
    print()
    print("4. List all tariff sources:")
    print('   python scripts/manage_sources.py --list')


if __name__ == "__main__":
    test_metadata_format()
    test_bundle_script()