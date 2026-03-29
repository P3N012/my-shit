"""
Initialize Database

Creates all database tables.

Run with: python scripts/init_db.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_db

def main():
    print("=" * 60)
    print("🔨 INITIALIZING DATABASE")
    print("=" * 60)
    print()
    
    try:
        init_db()
        print()
        print("=" * 60)
        print("✅ DATABASE INITIALIZED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERROR: {e}")
        print("=" * 60)
        print()
        print("Common issues:")
        print("  1. PostgreSQL not running")
        print("  2. Database doesn't exist (run: createdb insightplus_dev)")
        print("  3. Wrong credentials in .env file")
        print("  4. DATABASE_URL not set in .env")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()