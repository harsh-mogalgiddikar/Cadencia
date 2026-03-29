#!/usr/bin/env python3
"""
Run the A2A Treasury negotiation simulation from the repo root.

Usage:
    python run_simulation.py
    python run_simulation.py --mode autonomous
"""
import os
import subprocess
import sys

repo_root = os.path.dirname(os.path.abspath(__file__))
a2a_treasury = os.path.join(repo_root, "a2a-treasury")
script = os.path.join(a2a_treasury, "simulate_negotiation.py")

if not os.path.isfile(script):
    print("Error: a2a-treasury/simulate_negotiation.py not found.", file=sys.stderr)
    sys.exit(1)

result = subprocess.run(
    [sys.executable, script] + sys.argv[1:],
    cwd=a2a_treasury,
)
sys.exit(result.returncode)
