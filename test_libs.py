import sys
print("Testing imports...")

try:
    import numpy
    print(f"[OK] numpy imported: {numpy.__version__}")
except ImportError as e:
    print(f"[FAIL] numpy failed: {e}")

try:
    import pandas
    print(f"[OK] pandas imported: {pandas.__version__}")
except ImportError as e:
    print(f"[FAIL] pandas failed: {e}")

try:
    import sklearn
    print(f"[OK] sklearn imported: {sklearn.__version__}")
    from sklearn.neighbors import BallTree
    print("[OK] sklearn.neighbors.BallTree imported")
except ImportError as e:
    print(f"[FAIL] sklearn failed: {e}")

try:
    import osmnx
    print(f"[OK] osmnx imported: {osmnx.__version__}")
except ImportError as e:
    print(f"[FAIL] osmnx failed: {e}")

print("Done.")
