import sys
print("Testing all imports...")

try:
    import fastapi
    print(f"[OK] fastapi: {fastapi.__version__}")
except ImportError as e:
    print(f"[FAIL] fastapi: {e}")

try:
    import uvicorn
    print(f"[OK] uvicorn: {uvicorn.__version__}")
except ImportError as e:
    print(f"[FAIL] uvicorn: {e}")

try:
    import sqlalchemy
    print(f"[OK] sqlalchemy: {sqlalchemy.__version__}")
except ImportError as e:
    print(f"[FAIL] sqlalchemy: {e}")

try:
    import pydantic
    print(f"[OK] pydantic: {pydantic.__version__}")
except ImportError as e:
    print(f"[FAIL] pydantic: {e}")

try:
    from app.main import app
    print("[OK] app.main imported successfully")
except Exception as e:
    import traceback
    print(f"[FAIL] app.main import failed:")
    traceback.print_exc()

print("Done.")
