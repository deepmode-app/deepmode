#!/usr/bin/env python3
"""
Migration script: Add profile fields to users table

Usage:
    python migrations/migrate_add_user_profile_fields.py

This script will:
1. Check which database backend is being used (PostgreSQL or SQLite)
2. Add profile fields if they don't exist
3. Handle errors gracefully if columns already exist

New fields:
- first_name (text, nullable)
- last_name (text, nullable)
- organization (text, nullable)
- location (text, nullable) - kept for backward compatibility
- country (text, nullable)
- city (text, nullable)
- timezone (text, nullable)
- linkedin_url (text, nullable)
- avatar_url (text, nullable)
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
    new_fields = [
        "first_name",
        "last_name",
        "organization",
        "country",
        "city",
        "timezone",
        "linkedin_url",
        "avatar_url",
    ]
    
    for field in new_fields:
        try:
            cur.execute(f"""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS {field} TEXT;
            """)
            print(f"✓ Added {field} column (PostgreSQL)")
        except Exception as e:
            print(f"⚠ {field} column: {e}")

    conn.commit()
    cur.close()


def migrate_sqlite(conn):
    """Add columns to SQLite database"""
    cur = conn.cursor()
    
    # Check if columns already exist
    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]
    
    new_fields = [
        "first_name",
        "last_name",
        "organization",
        "location",  # kept for backward compatibility
        "country",
        "city",
        "timezone",
        "linkedin_url",
        "avatar_url",
    ]
    
    for field in new_fields:
        if field not in columns:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {field} TEXT;")
                print(f"✓ Added {field} column (SQLite)")
            except Exception as e:
                print(f"⚠ {field} column: {e}")
        else:
            print(f"✓ {field} column already exists (SQLite)")

    conn.commit()
    cur.close()


def main():
    # Check if DATABASE_URL is set (PostgreSQL) or we're using SQLite
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        backend = "postgres"
    else:
        backend = "sqlite"
    
    print(f"Running migration for database backend: {backend}")
    print("-" * 50)
    
    conn = get_conn()
    
    try:
        if backend == "postgres":
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

