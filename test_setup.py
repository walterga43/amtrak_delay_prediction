"""
Test script to verify all packages are installed correctly
"""

import sys
import os

print("="*60)
print("AMTRAK PROJECT SETUP TEST")
print("="*60)
print(f"\nPython version: {sys.version}")
print(f"Python path: {sys.executable}")

# Test package imports
packages_status = []

try:
    import pandas
    packages_status.append(f"✓ Pandas installed: {pandas.__version__}")
except ImportError as e:
    packages_status.append(f"✗ Pandas not installed: {e}")

try:
    import numpy
    packages_status.append(f"✓ NumPy installed: {numpy.__version__}")
except ImportError as e:
    packages_status.append(f"✗ NumPy not installed: {e}")

try:
    import matplotlib
    packages_status.append(f"✓ Matplotlib installed: {matplotlib.__version__}")
except ImportError as e:
    packages_status.append(f"✗ Matplotlib not installed: {e}")

try:
    import seaborn
    packages_status.append(f"✓ Seaborn installed: {seaborn.__version__}")
except ImportError as e:
    packages_status.append(f"✗ Seaborn not installed: {e}")

try:
    import schedule
    # Schedule doesn't have __version__, so just check if it imports
    packages_status.append(f"✓ Schedule installed: (version not available)")
except ImportError as e:
    packages_status.append(f"✗ Schedule not installed: {e}")

try:
    import requests
    packages_status.append(f"✓ Requests installed: {requests.__version__}")
except ImportError as e:
    packages_status.append(f"✗ Requests not installed: {e}")

try:
    import sklearn
    packages_status.append(f"✓ Scikit-learn installed: {sklearn.__version__}")
except ImportError as e:
    packages_status.append(f"✗ Scikit-learn not installed: {e}")

print("\n" + "-"*40)
print("PACKAGE STATUS:")
print("-"*40)
for status in packages_status:
    print(status)

# Test API connection
print("\n" + "-"*40)
print("API CONNECTION TEST:")
print("-"*40)
try:
    import requests
    response = requests.get("https://api-v3.amtraker.com/v3/trains", timeout=10)
    if response.status_code == 200:
        data = response.json()
        train_count = len(data.keys())
        print(f"✓ API is accessible")
        print(f"✓ Successfully retrieved data for {train_count} trains")
    else:
        print(f"✗ API returned status: {response.status_code}")
except Exception as e:
    print(f"✗ Could not connect to API: {str(e)}")

# Check project structure
print("\n" + "-"*40)
print("PROJECT STRUCTURE CHECK:")
print("-"*40)

current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# Check for required files
files_to_check = [
    "data_collector.py",
    "automated_collection.py",
    "requirements.txt"
]

for file in files_to_check:
    if os.path.exists(file):
        print(f"✓ Found: {file}")
    else:
        print(f"✗ Missing: {file}")

# Check for data directories
dirs_to_check = [
    "data",
    "data/raw",
    "data/historical"
]

for dir_path in dirs_to_check:
    if os.path.exists(dir_path):
        print(f"✓ Directory exists: {dir_path}")
    else:
        print(f"⚠ Directory missing: {dir_path} (will be created automatically)")

# Test if we can import your modules
print("\n" + "-"*40)
print("MODULE IMPORT TEST:")
print("-"*40)

try:
    from data_collector import AmtrackDataCollector
    print("✓ Can import AmtrackDataCollector from data_collector.py")
except ImportError as e:
    print(f"✗ Cannot import data_collector: {e}")

try:
    from automated_collection import HistoricalDataManager
    print("✓ Can import HistoricalDataManager from automated_collection.py")
except ImportError as e:
    print(f"✗ Cannot import automated_collection: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)

# Summary
print("\nSUMMARY:")
if all("✓" in status for status in packages_status):
    print("✓ All required packages are installed")
else:
    print("✗ Some packages are missing - check above for details")

print("\nNEXT STEPS:")
print("1. If all packages are installed, update your automated_collection.py with the fixed version")
print("2. Run: python automated_collection.py")
print("3. For data analysis, save and run the data_display.py script")