#!/usr/bin/env python3
"""Migration script for security updates."""

import os
import re
import sys
from pathlib import Path

print("Sarah AI Security Update Migration")
print("=" * 50)

# Check for potential issues
issues_found = []

# 1. Check pydantic v2 migration needs
print("\n1. Checking Pydantic v2 compatibility...")
pydantic_files = []
for root, dirs, files in os.walk("sarah"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, "r") as f:
                content = f.read()
                if "pydantic" in content.lower():
                    # Check for v1 patterns
                    if re.search(r"class.*\(BaseModel\):", content):
                        pydantic_files.append(filepath)
                    if "Config:" in content and "class Config:" in content:
                        issues_found.append(f"Pydantic v1 Config class in {filepath}")

if pydantic_files:
    print(f"   Found {len(pydantic_files)} files using Pydantic")
else:
    print("   ✓ No Pydantic usage found")

# 2. Check aiohttp ClientSession usage
print("\n2. Checking aiohttp ClientSession usage...")
aiohttp_files = []
for root, dirs, files in os.walk("sarah"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, "r") as f:
                content = f.read()
                if "aiohttp" in content:
                    aiohttp_files.append(filepath)
                    # Check for deprecated patterns
                    if "connector_owner=False" in content:
                        issues_found.append(f"Deprecated connector_owner in {filepath}")

print(f"   Found {len(aiohttp_files)} files using aiohttp")

# 3. Check FastAPI dependencies
print("\n3. Checking FastAPI compatibility...")
fastapi_files = []
for root, dirs, files in os.walk("sarah"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, "r") as f:
                content = f.read()
                if "fastapi" in content.lower():
                    fastapi_files.append(filepath)

print(f"   Found {len(fastapi_files)} files using FastAPI")

# 4. Summary
print("\n" + "=" * 50)
print("Migration Summary:")
print(
    f"Files to review: {len(pydantic_files) + len(aiohttp_files) + len(fastapi_files)}"
)

if issues_found:
    print("\nIssues Found:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print("\n✓ No compatibility issues detected!")

print("\nRecommended Actions:")
print("1. Update requirements: pip install -r requirements.txt --upgrade")
print("2. Run tests: pytest tests/")
print("3. Test critical paths manually")
print("4. Monitor logs for deprecation warnings")

# Check if we can import the new versions
print("\nChecking imports with new versions...")
try:
    import pydantic

    print(f"✓ Pydantic {pydantic.__version__} imported successfully")

    # Check for v2 features
    if hasattr(pydantic, "field_validator"):
        print("  ✓ Pydantic v2 confirmed")
except ImportError as e:
    print(f"✗ Pydantic import failed: {e}")

try:
    import aiohttp

    print(f"✓ aiohttp {aiohttp.__version__} imported successfully")
except ImportError as e:
    print(f"✗ aiohttp import failed: {e}")

try:
    import fastapi

    print(f"✓ FastAPI {fastapi.__version__} imported successfully")
except ImportError as e:
    print(f"✗ FastAPI import failed: {e}")
