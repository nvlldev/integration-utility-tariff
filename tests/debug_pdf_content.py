"""Debug PDF content to understand structure."""
import PyPDF2
from pathlib import Path

pdf_path = Path(__file__).parent / "test_download.pdf"

with open(pdf_path, 'rb') as f:
    pdf_reader = PyPDF2.PdfReader(f)
    text = pdf_reader.pages[0].extract_text()
    
    # Save full text for inspection
    with open("pdf_text_debug.txt", "w") as out:
        out.write(text)
    
    # Print lines around "Residential"
    lines = text.split('\n')
    
    print("=== Looking for Residential section ===")
    for i, line in enumerate(lines):
        if 'Residential' in line:
            print(f"\nFound at line {i}:")
            # Print context
            for j in range(max(0, i-2), min(len(lines), i+15)):
                print(f"{j:3d}: {lines[j]}")
    
    print("\n=== Looking for rate patterns ===")
    # Look for any lines with dollar signs
    for i, line in enumerate(lines):
        if '$' in line and ('kWh' in line or 'Service' in line or 'Facility' in line):
            print(f"{i:3d}: {line}")