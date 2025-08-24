#!/usr/bin/env python3
"""Simple runner script for Step 1 verification tests."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

if __name__ == "__main__":
    test_file = project_root / "tests" / "step1" / "test_step1_verification.py"
    
    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        sys.exit(1)
    
    # Run pytest with quiet mode
    exit_code = pytest.main([
        "-q",
        str(test_file),
        "-v",  # Verbose for better output
    ])
    
    sys.exit(exit_code)
