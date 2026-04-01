# scripts/compile_contract.py
# ONE-TIME UTILITY — run locally, not in production
# Output: blockchain/contracts/teal/escrow_approval.teal
#         blockchain/contracts/teal/escrow_clear.teal
#
# Usage: python scripts/compile_contract.py
#
# This script compiles the PyTeal source into static TEAL files.
# After running once, the TEAL files become permanent static assets
# checked into version control. Do NOT run this from application startup.

import sys
from pathlib import Path

# Add project root to path so imports work
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from pyteal import compileTeal, Mode
except ImportError:
    print("ERROR: pyteal is required for compilation.")
    print("Install it with: pip install pyteal")
    print("Note: pyteal is a dev-only dependency, not needed in production.")
    sys.exit(1)

from blockchain.contracts.treasury_escrow import approval_program, clear_program

OUT_DIR = PROJECT_ROOT / "blockchain" / "contracts" / "teal"
OUT_DIR.mkdir(parents=True, exist_ok=True)

with open(OUT_DIR / "escrow_approval.teal", "w") as f:
    f.write(compileTeal(approval_program(), mode=Mode.Application, version=10))

with open(OUT_DIR / "escrow_clear.teal", "w") as f:
    f.write(compileTeal(clear_program(), mode=Mode.Application, version=10))

print(f"TEAL files written to {OUT_DIR}")
