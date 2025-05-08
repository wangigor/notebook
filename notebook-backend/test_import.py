import sys
print(sys.path)
try:
    from app.db.dependencies import get_db_session
    print("Import successful!")
except ImportError as e:
    print(f"Import error: {e}")
