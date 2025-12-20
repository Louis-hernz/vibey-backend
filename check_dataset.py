import os
import sys

print("=" * 50)
print("CHECKING FOR DATASET.CSV")
print("=" * 50)

if os.path.exists("dataset.csv"):
    size = os.path.getsize("dataset.csv")
    print(f"✅ dataset.csv EXISTS! Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
else:
    print("❌ dataset.csv NOT FOUND!")
    print("Current directory:", os.getcwd())
    print("Files in current directory:")
    for f in os.listdir("."):
        print(f"  - {f}")
    sys.exit(1)

print("=" * 50)
