#!/usr/bin/env python3
"""
Migration script: Add project_name and notes columns to sessions table

Usage:
    python migrations/migrate_add_project_name_notes.py

This script will:
1. Check which database backend is being used (PostgreSQL or SQLite)
2. Add project_name and notes columns if they don't exist
3. Handle errors gracefully if columns already exist
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_conn, DB_BACKEND


def migrate_postgres(conn):
    """Add columns to PostgreSQL database"""
    cur = conn.cursor()
    try:
        # PostgreSQL supports IF NOT EXISTS
        cur.execute("""
            ALTER TABLE sessions 
            ADD COLUMN IF NOT EXISTS project_name VARCHAR(255);
        """)
        print("✓ Added project_name column (PostgreSQL)")
    except Exception as e:
        print(f"⚠ project_name column: {e}")

    try:
        cur.execute("""
            ALTER TABLE sessions 
            ADD COLUMN IF NOT EXISTS notes TEXT;
        """)
        print("✓ Added notes column (PostgreSQL)")
    except Exception as e:
        print(f"⚠ notes column: {e}")

    conn.commit()
    cur.close()


def migrate_sqlite(conn):
    """Add columns to SQLite database"""
    cur = conn.cursor()
    
    # Check if columns already exist
    cur.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cur.fetchall()]
    
    if "project_name" not in columns:
        try:
            cur.execute("ALTER TABLE sessions ADD COLUMN project_name TEXT;")
            print("✓ Added project_name column (SQLite)")
        except Exception as e:
            print(f"⚠ project_name column: {e}")
    else:
        print("✓ project_name column already exists (SQLite)")

    if "notes" not in columns:
        try:
            cur.execute("ALTER TABLE sessions ADD COLUMN notes TEXT;")
            print("✓ Added notes column (SQLite)")
        except Exception as e:
            print(f"⚠ notes column: {e}")
    else:
        print("✓ notes column already exists (SQLite)")

    conn.commit()
    cur.close()


def main():
    print(f"Running migration for database backend: {DB_BACKEND}")
    print("-" * 50)
    
    conn = get_conn()
    
    try:
        if DB_BACKEND == "postgres":
            migrate_postgres(conn)
        else:
            migrate_sqlite(conn)
        
        print("-" * 50)
        print("✓ Migration completed successfully!")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

