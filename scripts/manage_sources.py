#!/usr/bin/env python3
"""Script to manage tariff sources for the Utility Tariff integration.

The JSON structure uses source prefixes to determine behavior:
- http:// or https:// - Download from URL each time
- file:// - Load from bundled data folder
- Just filename - Treated as file:// (backward compatibility)
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
import shutil


def get_source_type(source: str) -> str:
    """Determine source type from prefix."""
    if source.startswith(('http://', 'https://')):
        return 'url'
    elif source.startswith('file://'):
        return 'file'
    elif '://' not in source:
        # No protocol, assume local file
        return 'file'
    else:
        return 'unknown'


def download_pdf(url: str, output_path: Path) -> bool:
    """Download a PDF from a URL."""
    try:
        print(f"Downloading from: {url}")
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded {len(response.content):,} bytes to {output_path.name}")
        return True
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False


def copy_local_file(source: str, output_path: Path) -> bool:
    """Copy a local file to the data directory."""
    try:
        # Handle file:// URLs
        if source.startswith('file://'):
            source = source[7:]  # Remove file:// prefix
        
        source_path = Path(source)
        if not source_path.exists():
            print(f"Error: File not found: {source}")
            return False
        
        shutil.copy2(source_path, output_path)
        print(f"Copied {source_path.name} to {output_path.name}")
        return True
    except Exception as e:
        print(f"Error copying file: {e}")
        return False


def extract_filename_from_source(source: str) -> str:
    """Extract filename from source."""
    source_type = get_source_type(source)
    
    if source_type == 'url':
        # Extract from URL
        parsed = urlparse(source)
        filename = Path(unquote(parsed.path)).name
        if filename.endswith('.pdf'):
            return filename
    elif source_type == 'file':
        # Extract from file path
        if source.startswith('file://'):
            filename = source[7:]
        else:
            filename = source
        return Path(filename).name
    
    # Fallback
    return f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"


def add_or_update_source_entry(provider: str, service_type: str, source: str, 
                              effective_date: str = None, description: str = None):
    """Add or update a source entry in the metadata."""
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    data_dir = component_dir / "data"
    metadata_file = component_dir / "sources.json"
    
    # Load existing metadata
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {"version": "3.0", "providers": {}}
    
    # Ensure structure exists
    if provider not in metadata["providers"]:
        metadata["providers"][provider] = {}
    if service_type not in metadata["providers"][provider]:
        metadata["providers"][provider][service_type] = []
    
    # Determine source type and adjust source format if needed
    source_type = get_source_type(source)
    
    if source_type == 'file':
        # For local files, ensure it uses file:// prefix with just the filename
        filename = extract_filename_from_source(source)
        
        # If source is a local file path, copy it to data directory
        if not source.startswith('file://') or '/' in source[7:]:
            # This is a full path, we need to copy the file
            output_path = data_dir / filename
            if source_type == 'file' and not source.startswith('file://'):
                success = copy_local_file(source, output_path)
            else:
                success = copy_local_file(source, output_path)
            
            if not success:
                return False
        
        # Update source to use file:// with just filename
        source = f"file://{filename}"
    
    # Auto-detect effective date from filename if not provided
    if not effective_date:
        filename = extract_filename_from_source(source)
        effective_date = extract_effective_date_from_filename(filename)
    
    # Create new entry
    new_entry = {
        "source": source,
        "effective_date": effective_date,
        "description": description or f"{service_type.title()} rates effective {effective_date}"
    }
    
    # Check if this exact source already exists
    entries = metadata["providers"][provider][service_type]
    source_exists = False
    
    for i, entry in enumerate(entries):
        if entry.get("source") == source:
            # Update existing entry
            entries[i] = new_entry
            source_exists = True
            print(f"Updated existing entry for {source}")
            break
    
    if not source_exists:
        # Add new entry
        entries.append(new_entry)
        print(f"Added new entry for {source}")
    
    # Sort entries by effective date (newest first)
    entries.sort(key=lambda x: x.get("effective_date", ""), reverse=True)
    
    # Save updated metadata
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nUpdated {provider} {service_type}:")
    print(f"  Total versions: {len(entries)}")
    print(f"  Latest: {entries[0]['effective_date']}")
    print(f"  Source: {entries[0]['source']}")
    
    return True


def extract_effective_date_from_filename(filename: str) -> str:
    """Extract effective date from filename."""
    import re
    
    # Try different date patterns
    patterns = [
        r'(\d{2})\.(\d{2})\.(\d{4})',  # MM.DD.YYYY
        r'(\d{2})-(\d{2})-(\d{4})',    # MM-DD-YYYY
        r'(\d{4})-(\d{2})-(\d{2})',    # YYYY-MM-DD
        r'as[_\s]of[_\s-]*(\d{2})-(\d{2})-(\d{4})',  # as_of-MM-DD-YYYY
        r'(\d{2})-(\d{2})-(\d{2})',    # MM-DD-YY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                # Check if it's YYYY-MM-DD format
                if len(groups[0]) == 4:
                    year, month, day = groups
                else:
                    month, day, year = groups
                    if len(year) == 2:
                        year = f"20{year}"
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return datetime.now().strftime("%Y-%m-%d")


def list_sources():
    """List all tariff sources."""
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    data_dir = component_dir / "data"
    metadata_file = component_dir / "sources.json"
    
    if not metadata_file.exists():
        print("No tariff sources found.")
        return
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    print(f"\nTariff Sources (version {metadata.get('version', 'unknown')}):")
    print("=" * 80)
    
    for provider, services in metadata.get("providers", {}).items():
        print(f"\n{provider.replace('_', ' ').title()}:")
        for service_type, entries in services.items():
            print(f"\n  {service_type.title()} Service:")
            
            for i, entry in enumerate(entries):
                source = entry['source']
                source_type = get_source_type(source)
                
                # Check file existence for file:// sources
                status = ""
                if source_type == 'file':
                    filename = source[7:] if source.startswith('file://') else source
                    if (data_dir / filename).exists():
                        size = (data_dir / filename).stat().st_size
                        status = f" [{size:,} bytes]"
                    else:
                        status = " [FILE MISSING]"
                elif source_type == 'url':
                    status = " [DOWNLOAD]"
                
                latest = " (LATEST)" if i == 0 else ""
                print(f"    {i+1}. {entry['effective_date']}{latest}")
                print(f"       {entry.get('description', 'No description')}")
                print(f"       Source: {source}{status}")


def download_source(provider: str, service_type: str):
    """Download PDFs from URL sources."""
    component_dir = Path(__file__).parent.parent / "custom_components" / "utility_tariff"
    data_dir = component_dir / "data"
    metadata_file = component_dir / "sources.json"
    
    if not metadata_file.exists():
        print("No tariff sources metadata found.")
        return
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    entries = metadata.get("providers", {}).get(provider, {}).get(service_type, [])
    if not entries:
        print(f"No entries found for {provider} {service_type}")
        return
    
    downloaded = 0
    for entry in entries:
        source = entry['source']
        if source.startswith(('http://', 'https://')):
            filename = extract_filename_from_source(source)
            output_path = data_dir / filename
            
            print(f"\nDownloading: {entry.get('description', filename)}")
            if download_pdf(source, output_path):
                downloaded += 1
                # Update entry to use file:// after download
                entry['source'] = f"file://{filename}"
    
    if downloaded > 0:
        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"\nDownloaded {downloaded} PDF(s) and updated metadata")


def main():
    parser = argparse.ArgumentParser(
        description="Manage tariff sources for Utility Tariff integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Source types (auto-detected by prefix):
  http:// or https:// - Download from URL when needed
  file://             - Use bundled file from data directory
  /path/to/file       - Copy local file to data directory

Examples:
  # Add URL source (will download when needed)
  %(prog)s xcel_energy electric --source https://example.com/rates.pdf
  
  # Add local file (will copy to data directory)
  %(prog)s xcel_energy gas --source /path/to/rates.pdf
  
  # Add with custom date
  %(prog)s xcel_energy electric --source rates.pdf --effective-date 2025-01-01
  
  # Download all URL sources for a provider
  %(prog)s xcel_energy electric --download
  
  # List all tariff sources
  %(prog)s --list
        """
    )
    
    parser.add_argument("provider", nargs='?', help="Provider name (e.g., xcel_energy)")
    parser.add_argument("service_type", nargs='?', help="Service type (electric or gas)")
    parser.add_argument("--source", help="Source URL or file path")
    parser.add_argument("--effective-date", help="Effective date (YYYY-MM-DD)")
    parser.add_argument("--description", help="Description of the PDF")
    parser.add_argument("--list", action="store_true", help="List all tariff sources")
    parser.add_argument("--download", action="store_true", help="Download all URL sources for provider/service")
    
    args = parser.parse_args()
    
    # Handle list command
    if args.list:
        list_sources()
        return
    
    # Check required arguments
    if not args.provider or not args.service_type:
        parser.error("Provider and service_type are required unless using --list")
    
    # Handle download command
    if args.download:
        download_source(args.provider, args.service_type)
        return
    
    # Handle add/update
    if not args.source:
        parser.error("Must specify --source to add/update an entry")
    
    # Add or update entry
    success = add_or_update_source_entry(
        args.provider,
        args.service_type,
        args.source,
        args.effective_date,
        args.description
    )
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()