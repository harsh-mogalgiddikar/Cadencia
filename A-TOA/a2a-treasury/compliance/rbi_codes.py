"""
compliance/rbi_codes.py — RBI purpose codes for FEMA compliance.

Reserve Bank of India classifies all cross-border payments by purpose code.
These codes are mandatory for SWIFT/NEFT transfers and FEMA reporting.
"""
from __future__ import annotations

RBI_PURPOSE_CODES: dict[str, str] = {
    "P0101": "Export of goods — software services",
    "P0102": "Export of goods — non-software services",
    "P0103": "Export of goods — merchandise",
    "P0201": "Import of goods — software services",
    "P0202": "Import of goods — non-software services",
    "P0203": "Import of goods — merchandise",
    "P0301": "Transportation — freight",
    "P0401": "Travel",
    "P1001": "Advance payment for import",
    "P1301": "Capital account — ODI",
    "P1302": "Capital account — FDI",
}

# Default purpose code for B2B trade on this platform
DEFAULT_TRADE_PURPOSE_CODE = "P0103"  # Export/Import merchandise
