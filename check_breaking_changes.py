#!/usr/bin/env python3
"""Check for potential breaking changes in updated dependencies."""

import subprocess
import sys

# Major version changes that might have breaking changes
MAJOR_CHANGES = [
    ("aiohttp", "3.9.1", "3.11.11"),
    ("langchain", "0.1.1", "0.3.15"),
    ("langchain-community", "0.0.10", "0.3.15"),
    ("cryptography", "41.0.7", "45.0.0"),
    ("pydantic", "2.5.3", "2.10.4"),
    ("fastapi", "0.109.0", "0.115.6"),
]

print("Security Update Breaking Change Analysis")
print("=" * 50)
print()

print("Major Version Changes:")
for pkg, old_ver, new_ver in MAJOR_CHANGES:
    print(f"  {pkg}: {old_ver} → {new_ver}")

print("\nPotential Issues to Check:")
print("1. aiohttp: Check all async HTTP client usage")
print("2. langchain: Major API changes likely - review all AI service calls")
print("3. pydantic: Check model definitions and validation")
print("4. cryptography: Verify encryption/decryption operations")
print("5. fastapi: Check middleware and dependency injection")

print("\nRecommended Testing Order:")
print("1. Run unit tests: pytest tests/")
print("2. Test authentication flow (cryptography)")
print("3. Test AI operations (langchain)")
print("4. Test HTTP operations (aiohttp)")
print("5. Test API endpoints (fastapi)")
print("6. Full integration test")

print("\nTo check import compatibility:")
print("python -c 'import sarah'")

# Try basic imports
print("\nChecking basic imports...")
try:
    import fastapi

    print(f"✓ FastAPI {fastapi.__version__}")
except ImportError as e:
    print(f"✗ FastAPI import failed: {e}")

try:
    import aiohttp

    print(f"✓ aiohttp {aiohttp.__version__}")
except ImportError as e:
    print(f"✗ aiohttp import failed: {e}")

try:
    import pydantic

    print(f"✓ Pydantic {pydantic.__version__}")
except ImportError as e:
    print(f"✗ Pydantic import failed: {e}")

print("\nNext steps:")
print("1. pip install -r requirements.txt --upgrade")
print("2. Run this script again to verify imports")
print("3. Run test suite")
print("4. Update code for any breaking changes")
