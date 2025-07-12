#!/usr/bin/env python3
"""
Simple test runner for the OSM MCP Server tests.

This script runs the search_category tests to verify the fix works correctly.
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Run the tests for the search_category fix."""
    
    # Add the src directory to the Python path
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    sys.path.insert(0, str(src_path))
    
    print("🧪 Running OSM MCP Server Tests")
    print("=" * 50)
    
    # Check if pytest is available
    try:
        import pytest
        print("✅ pytest is available")
    except ImportError:
        print("❌ pytest is not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio"])
        print("✅ pytest installed")
    
    # Run the tests
    test_file = Path(__file__).parent / "test_search_category.py"
    
    print(f"\n🔍 Running tests from: {test_file}")
    print("-" * 50)
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        str(test_file), 
        "-v", 
        "--tb=short"
    ])
    
    print("\n" + "=" * 50)
    if result.returncode == 0:
        print("✅ All tests passed! The search_category fix is working correctly.")
    else:
        print("❌ Some tests failed. Please check the output above.")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())